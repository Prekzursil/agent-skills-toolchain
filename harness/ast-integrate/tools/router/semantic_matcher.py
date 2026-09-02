"""Second-stage semantic capability matcher over a version-pinned local model (IMP-0390).

Stage one of routing is :mod:`router.lexical` (token Jaccard, the IMP-0388
linter's instrument).  This module is stage two: it embeds the query and every
capability description with the *pinned* local concept-embedding model
(:mod:`router.embed_model`) and ranks by integer cosine.  The exact question the
unit answers is whether this stage recovers the paraphrase pairs the lexical
stage provably cannot see, measured on the planted-mutant control set derived
from IMP-0388 (``tools/router/data/planted_mutants_imp0388.json``).

Contract points the probes rely on:

* :func:`match` never falls back to lexical ranking.  When the pinned model is
  absent, has the wrong id, or does not match the pinned digest, the result is
  ``status="DEGRADED"`` with a typed ``code`` (``PINNED-MODEL-*``), an empty
  ranking and ``lexical_results_suppressed=True``.  A lexical row is never
  relabelled as semantic; the two stages carry distinct ``method`` tags.
* Ranking is deterministic: no RNG, integer scores, tie-break on
  ``capability_id``; ``ranking_bytes()`` is the canonical JSON used for
  byte-identity checks.  ``seed`` is the control-set seed echoed into rows.
* Every path is resolved relative to this file, so a mirror of the tree loads
  the mirror's model, pin and control set.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from router import embed_model as em
from router.lexical import cap_id, cap_text, jaccard_int, lexical_rank, shared_tokens, tokenize

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

MODEL_REL = "tools/router/models/imp0390-embed-v1.json"
PIN_REL = "tools/router/models/imp0390-embed-v1.pin.json"
PLANTED_REL = "tools/router/data/planted_mutants_imp0388.json"
MODEL_PATH = REPO / MODEL_REL
PIN_PATH = REPO / PIN_REL
PLANTED_PATH = REPO / PLANTED_REL

MODEL_ID = em.MODEL_ID
METHOD = "semantic-concept-embed"
STAGE = "semantic"
PIN_SCHEMA = "ast.router.embed-model-pin/v1"
PLANTED_SCHEMA = "ast.router.planted-control/v1"
_PIN_KEYS = ("schema", "model_id", "version", "algo", "path", "sha256", "document_digest", "dim", "seed")
_QUERY_LISTS = ("verbatim_queries", "paraphrase_queries")


class PinError(ValueError):
    """The pin document is missing a field or names the wrong schema."""


class PlantedSetError(ValueError):
    """The planted control set violates its own construction contract."""


# ------------------------------------------------------------------------ pin


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def read_pin(pin_path: Path | str | None = None) -> dict[str, Any]:
    """Parse and validate the pin document; raise on absence or malformation."""
    p = Path(pin_path) if pin_path is not None else PIN_PATH
    if not p.is_file():
        raise FileNotFoundError(f"pin file not found: {p}")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PinError(f"pin file is not valid JSON: {exc}") from exc
    if not isinstance(doc, Mapping):
        raise PinError("pin document must be a JSON object")
    missing = [k for k in _PIN_KEYS if k not in doc]
    if missing:
        raise PinError(f"pin document missing keys: {missing}")
    if doc["schema"] != PIN_SCHEMA:
        raise PinError(f"pin schema {doc['schema']!r} != {PIN_SCHEMA!r}")
    for key in ("model_id", "version", "algo", "path", "sha256", "document_digest"):
        if not isinstance(doc[key], str) or not doc[key]:
            raise PinError(f"pin field {key!r} must be a non-empty string")
    for key in ("dim", "seed"):
        if not isinstance(doc[key], int) or isinstance(doc[key], bool):
            raise PinError(f"pin field {key!r} must be an integer")
    for key in ("sha256", "document_digest"):
        if len(doc[key]) != 64 or any(c not in "0123456789abcdef" for c in doc[key]):
            raise PinError(f"pin field {key!r} must be a lower-case sha256 hex digest")
    return dict(doc)


def pin_identity(
    pin_path: Path | str | None = None, model_path: Path | str | None = None
) -> dict[str, Any]:
    """Pinned vs live identity of the model file (never raises).

    ``digest_matches_pin`` is True only when the pin parses and the live model
    file's sha256 equals the pinned one.  ``path`` is repo-relative so callers
    can rebuild the absolute path against their own tree root.
    """
    pin_p = Path(pin_path) if pin_path is not None else PIN_PATH
    try:
        pin = read_pin(pin_p)
        detail = ""
    except (FileNotFoundError, PinError) as exc:
        pin = None
        detail = f"{type(exc).__name__}: {exc}"
    model_p = (
        Path(model_path)
        if model_path is not None
        else (REPO / pin["path"] if pin else MODEL_PATH)
    )
    live = em.file_digest(model_p) if model_p.is_file() else None
    pinned = pin["sha256"] if pin else None
    return {
        "model_id": pin["model_id"] if pin else MODEL_ID,
        "version": pin["version"] if pin else None,
        "algo": pin["algo"] if pin else None,
        "dim": pin["dim"] if pin else None,
        "seed": pin["seed"] if pin else None,
        "path": pin["path"] if pin else MODEL_REL,
        "pin_path": _rel(pin_p),
        "pinned_sha256": pinned,
        "pinned_document_digest": pin["document_digest"] if pin else None,
        "live_sha256": live,
        "model_present": live is not None,
        "digest_matches_pin": live is not None and pinned is not None and live == pinned,
        "detail": detail,
    }


def _load_pinned(model_path: Path | str | None = None) -> tuple[em.ModelLoad, dict[str, Any] | None]:
    """Load ``model_path`` (default: the pinned path) and enforce the pin."""
    try:
        pin = read_pin()
    except (FileNotFoundError, PinError) as exc:
        return (
            em.ModelLoad(
                em.STATUS_DEGRADED,
                em.CODE_ABSENT,
                str(PIN_PATH),
                detail=f"pin unavailable: {type(exc).__name__}: {exc}",
            ),
            None,
        )
    path = Path(model_path) if model_path is not None else REPO / pin["path"]
    load = em.load_model(
        path,
        expected_id=pin["model_id"],
        pinned_digest=pin["document_digest"],
        pinned_file_sha256=pin["sha256"],
    )
    return load, pin


# ---------------------------------------------------------------------- match


@dataclass(frozen=True)
class MatchResult:
    """Outcome of one semantic ranking; ``ranking`` is empty when DEGRADED."""

    status: str
    stage: str
    code: str
    query: str
    k: int
    seed: int | None
    model_id: str | None
    model_digest: str | None
    ranking: list[dict[str, Any]] = field(default_factory=list)
    lexical_results_suppressed: bool = False
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == em.STATUS_OK

    def top_ids(self) -> list[str]:
        return [row["capability_id"] for row in self.ranking]

    def ranking_bytes(self) -> bytes:
        """Canonical JSON of the ranking rows (the byte-identity surface)."""
        return json.dumps(
            self.ranking, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")

    def ranking_sha256(self) -> str:
        return hashlib.sha256(self.ranking_bytes()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "stage": self.stage,
            "code": self.code,
            "query": self.query,
            "k": self.k,
            "seed": self.seed,
            "model_id": self.model_id,
            "model_digest": self.model_digest,
            "ranking": list(self.ranking),
            "ranking_sha256": self.ranking_sha256(),
            "lexical_results_suppressed": self.lexical_results_suppressed,
            "detail": self.detail,
        }


def _check_args(query: str, k: int, seed: int | None) -> None:
    if not isinstance(query, str):
        raise TypeError(f"query must be str, got {type(query).__name__}")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError(f"k must be an integer >= 1, got {k!r}")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise TypeError("seed must be an int or None")


def _capabilities(caps: Iterable[Mapping[str, Any]]) -> list[tuple[str, str]]:
    """``(capability_id, description)`` pairs; ids must be unique and non-empty."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for cap in caps:
        if not isinstance(cap, Mapping):
            raise TypeError(f"capabilities must be mappings, got {type(cap).__name__}")
        cid = cap_id(cap)
        if not cid:
            raise ValueError("capability without an id")
        if cid in seen:
            raise ValueError(f"duplicate capability_id {cid!r}")
        seen.add(cid)
        out.append((cid, cap_text(cap)))
    return out


def _rank(
    model: em.EmbedModel,
    query: str,
    caps: Sequence[tuple[str, str]],
    k: int,
    seed: int | None,
) -> list[dict[str, Any]]:
    """Top-``k`` capabilities by integer cosine; non-positive scores are dropped."""
    qv = model.embed(query)
    if not any(qv):
        return []
    scored: list[tuple[int, str]] = []
    for cid, text in caps:
        score = em.cosine_e9(qv, model.embed(text))
        if score > 0:
            scored.append((score, cid))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [
        {
            "rank": rank,
            "capability_id": cid,
            "cosine_e9": score,
            "method": METHOD,
            "model_id": model.model_id,
            "seed": seed,
        }
        for rank, (score, cid) in enumerate(scored[:k], 1)
    ]


def match(
    query: str,
    caps: Iterable[Mapping[str, Any]],
    k: int = 5,
    seed: int | None = None,
    model_path: Path | str | None = None,
) -> MatchResult:
    """Semantic top-``k`` for ``query`` under the pinned model, or a typed DEGRADED result."""
    _check_args(query, k, seed)
    rows = _capabilities(caps)
    load, pin = _load_pinned(model_path)
    if not load.ok or load.model is None:
        return MatchResult(
            status=em.STATUS_DEGRADED,
            stage=STAGE,
            code=load.code,
            query=query,
            k=k,
            seed=seed,
            model_id=pin["model_id"] if pin else None,
            model_digest=None,
            ranking=[],
            lexical_results_suppressed=True,
            detail=load.detail,
        )
    return MatchResult(
        status=em.STATUS_OK,
        stage=STAGE,
        code=em.CODE_OK,
        query=query,
        k=k,
        seed=seed,
        model_id=load.model.model_id,
        model_digest=pin["sha256"] if pin else load.digest,
        ranking=_rank(load.model, query, rows, k, seed),
        lexical_results_suppressed=False,
        detail="",
    )


# ------------------------------------------------------------- control set


def validate_planted(doc: Any) -> None:
    """Raise :class:`PlantedSetError` unless ``doc`` honours the control-set contract.

    Verbatim queries must equal their target's description; paraphrase queries
    and the planted pair must share *no* content token with their target under
    the lexical tokenizer (that zero is what makes the lexical miss provable).
    """
    if not isinstance(doc, Mapping):
        raise PlantedSetError("control set must be a JSON object")
    if doc.get("schema") != PLANTED_SCHEMA:
        raise PlantedSetError(f"control-set schema {doc.get('schema')!r} != {PLANTED_SCHEMA!r}")
    for key in ("seed", "k"):
        if not isinstance(doc.get(key), int) or isinstance(doc.get(key), bool):
            raise PlantedSetError(f"{key} must be an integer")
    if doc["k"] < 1:
        raise PlantedSetError("k must be >= 1")
    caps = doc.get("capabilities")
    if not isinstance(caps, list) or not caps:
        raise PlantedSetError("capabilities must be a non-empty list")
    by_id: dict[str, str] = {}
    for cap in caps:
        if not isinstance(cap, Mapping):
            raise PlantedSetError("each capability must be an object")
        cid, text = cap.get("capability_id"), cap.get("description")
        if not isinstance(cid, str) or not cid:
            raise PlantedSetError("capability_id must be a non-empty string")
        if not isinstance(text, str) or not tokenize(text):
            raise PlantedSetError(f"capability {cid!r} needs a description with content tokens")
        if cid in by_id:
            raise PlantedSetError(f"duplicate capability_id {cid!r}")
        by_id[cid] = text
    for key in _QUERY_LISTS:
        queries = doc.get(key)
        if not isinstance(queries, list) or not queries:
            raise PlantedSetError(f"{key} must be a non-empty list")
        for i, q in enumerate(queries):
            if not isinstance(q, Mapping):
                raise PlantedSetError(f"{key}[{i}] must be an object")
            text, target = q.get("query"), q.get("capability_id")
            if not isinstance(text, str) or not tokenize(text):
                raise PlantedSetError(f"{key}[{i}] needs a query with content tokens")
            if target not in by_id:
                raise PlantedSetError(f"{key}[{i}] targets unknown capability {target!r}")
            if key == "verbatim_queries" and text != by_id[target]:
                raise PlantedSetError(f"{key}[{i}] is not the verbatim description of {target!r}")
            if key == "paraphrase_queries":
                shared = shared_tokens(text, by_id[target])
                if shared:
                    raise PlantedSetError(
                        f"{key}[{i}] shares tokens {shared} with its target {target!r}"
                    )
    pair = doc.get("imp0388_planted_pair")
    if not isinstance(pair, Mapping):
        raise PlantedSetError("imp0388_planted_pair must be an object")
    left, right = pair.get("left_id"), pair.get("right_id")
    if left not in by_id or right not in by_id or left == right:
        raise PlantedSetError("imp0388_planted_pair must name two distinct known capabilities")
    shared = shared_tokens(by_id[left], by_id[right])
    if shared:
        raise PlantedSetError(f"planted pair shares tokens {shared}; lexical would see it")


def load_planted(path: Path | str | None = None) -> dict[str, Any]:
    """Load and validate the planted-mutant control set (built by ``router.build_pinned_model``)."""
    p = Path(path) if path is not None else PLANTED_PATH
    if not p.is_file():
        raise FileNotFoundError(
            f"planted control set not found: {p} "
            "(run: PYTHONPATH=tools python3 -m router.build_pinned_model)"
        )
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlantedSetError(f"control set is not valid JSON: {exc}") from exc
    validate_planted(doc)
    return doc


# ------------------------------------------------------------ measurements


def measure_recall(
    queries: Iterable[Mapping[str, Any]],
    caps: Iterable[Mapping[str, Any]],
    k: int,
    seed: int | None,
    model_path: Path | str | None = None,
) -> dict[str, Any]:
    """Recall@k of the lexical and the semantic stage over ``queries``.

    A query hits when its ``capability_id`` is among the stage's top-``k``.  The
    two stages are measured independently: a DEGRADED semantic stage scores
    zero semantic hits rather than borrowing the lexical ranking.
    """
    _check_args("", k, seed)
    rows_in = _capabilities(caps)
    cap_list = [{"capability_id": cid, "description": text} for cid, text in rows_in]
    by_id = dict(rows_in)
    load, pin = _load_pinned(model_path)
    model = load.model if load.ok else None
    rows: list[dict[str, Any]] = []
    lex_hits = sem_hits = 0
    for i, q in enumerate(queries):
        if not isinstance(q, Mapping):
            raise TypeError("queries must be mappings")
        qtext = str(q["query"])
        target = str(q["capability_id"])
        if target not in by_id:
            raise ValueError(f"query targets unknown capability {target!r}")
        qid = str(q.get("query_id") or f"q{i + 1}")
        klass = str(q.get("class") or ("verbatim" if qtext == by_id[target] else "paraphrase"))
        lex_rows = lexical_rank(qtext, cap_list, k=k, seed=seed)
        lex_top = [r["capability_id"] for r in lex_rows]
        lex_hit = target in lex_top
        lex_hits += int(lex_hit)
        if model is not None:
            sem_rows = _rank(model, qtext, rows_in, k, seed)
            sem_top = [r["capability_id"] for r in sem_rows]
            sem_hit = target in sem_top
            sem_status, sem_code = em.STATUS_OK, em.CODE_OK
            hit_row = next((r for r in sem_rows if r["capability_id"] == target), None)
            sem_rank = hit_row["rank"] if hit_row else None
            sem_cos = hit_row["cosine_e9"] if hit_row else model.similarity_e9(qtext, by_id[target])
        else:
            sem_top, sem_hit = [], False
            sem_status, sem_code = em.STATUS_DEGRADED, load.code
            sem_rank, sem_cos = None, None
        sem_hits += int(sem_hit)
        rows.append(
            {
                "query_id": qid,
                "class": klass,
                "target_id": target,
                "lexical_top": lex_top,
                "lexical_hit": lex_hit,
                "lexical_jaccard_e9": jaccard_int(tokenize(qtext), tokenize(by_id[target])),
                "semantic_top": sem_top,
                "semantic_hit": sem_hit,
                "semantic_rank": sem_rank,
                "semantic_cosine_e9": sem_cos,
                "semantic_status": sem_status,
                "semantic_code": sem_code,
            }
        )
    n = len(rows)
    return {
        "n": n,
        "k": k,
        "seed": seed,
        "lexical_hits": lex_hits,
        "semantic_hits": sem_hits,
        "lexical_recall_at_k": (lex_hits / n) if n else 0.0,
        "semantic_recall_at_k": (sem_hits / n) if n else 0.0,
        "semantic_status": em.STATUS_OK if model is not None else em.STATUS_DEGRADED,
        "semantic_code": em.CODE_OK if model is not None else load.code,
        "model_id": model.model_id if model is not None else (pin["model_id"] if pin else None),
        "model_digest": pin["sha256"] if (pin and model is not None) else None,
        "rows": rows,
    }


def pair_scores(
    left: str,
    right: str,
    seed: int | None = None,
    model_path: Path | str | None = None,
) -> dict[str, Any]:
    """Lexical Jaccard and semantic cosine between two descriptions.

    ``semantic_cosine_e9`` is ``None`` (not 0) when the pinned model is
    unavailable, so a degraded stage can never be read as "measured zero".
    """
    for name, text in (("left", left), ("right", right)):
        if not isinstance(text, str):
            raise TypeError(f"{name} must be str, got {type(text).__name__}")
    _check_args("", 1, seed)
    load, pin = _load_pinned(model_path)
    out: dict[str, Any] = {
        "seed": seed,
        "lexical_jaccard_e9": jaccard_int(tokenize(left), tokenize(right)),
        "lexical_shared_tokens": shared_tokens(left, right),
        "lexical_method": "lexical-jaccard",
        "semantic_method": METHOD,
        "semantic_status": load.status,
        "semantic_code": load.code,
        "model_id": load.model.model_id if load.ok and load.model else (pin["model_id"] if pin else None),
        "semantic_cosine_e9": None,
        "semantic_shared_concepts": [],
    }
    if load.ok and load.model is not None:
        model = load.model
        out["semantic_cosine_e9"] = model.similarity_e9(left, right)
        out["semantic_shared_concepts"] = sorted(
            set(model.concepts_of(left)) & set(model.concepts_of(right))
        )
    return out


__all__ = [
    "MATCH_RESULT_FIELDS",
    "METHOD",
    "MODEL_ID",
    "MODEL_PATH",
    "MODEL_REL",
    "MatchResult",
    "PIN_PATH",
    "PIN_REL",
    "PIN_SCHEMA",
    "PLANTED_PATH",
    "PLANTED_REL",
    "PLANTED_SCHEMA",
    "PinError",
    "PlantedSetError",
    "STAGE",
    "load_planted",
    "match",
    "measure_recall",
    "pair_scores",
    "pin_identity",
    "read_pin",
    "validate_planted",
]

MATCH_RESULT_FIELDS = tuple(MatchResult.__dataclass_fields__)
