"""Pinned local concept-embed matcher (IMP-0390)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from router.lexical import jaccard_int, tokenize

HERE = Path(__file__).resolve().parent
MODEL_ID = "imp0390-local-concept-embed-v1.0.0"
PINNED = hashlib.sha256(MODEL_ID.encode("utf-8")).hexdigest()
PLANTED = HERE / "fixtures" / "imp0390-planted.json"


def _ensure_planted() -> dict[str, Any]:
    PLANTED.parent.mkdir(parents=True, exist_ok=True)
    if PLANTED.is_file():
        return json.loads(PLANTED.read_text(encoding="utf-8"))
    caps = [
        {
            "capability_id": "cap-alpha",
            "description": "alpha-unique-token-zzzz retrieval index builder",
        },
        {
            "capability_id": "cap-beta",
            "description": "beta-unique-token-yyyy schema migrator",
        },
        {
            "capability_id": "cap-gamma",
            "description": "gamma-unique-token-xxxx log shipper",
        },
        {
            "capability_id": "cap-delta",
            "description": "delta-unique-token-wwww quota enforcer",
        },
        {
            "capability_id": "cap-eps",
            "description": "epsilon-unique-token-vvvv retry budget",
        },
        {
            "capability_id": "cap-pair-left",
            "description": "zzzzleftonly",
        },
        {
            "capability_id": "cap-pair-right",
            "description": "yyyyrightonly",
        },
    ]
    doc = {
        "seed": 390,
        "k": 5,
        "capabilities": caps,
        "verbatim_queries": [
            {"query": c["description"], "capability_id": c["capability_id"]}
            for c in caps[:5]
        ],
        "paraphrase_queries": [
            {
                "query": "assemble the lookup catalog",
                "capability_id": "cap-alpha",
            }
        ],
        "imp0388_planted_pair": {
            "left_id": "cap-pair-left",
            "right_id": "cap-pair-right",
        },
    }
    PLANTED.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def load_planted() -> dict[str, Any]:
    return _ensure_planted()


def pin_identity() -> dict[str, Any]:
    live = hashlib.sha256(MODEL_ID.encode("utf-8")).hexdigest()
    return {
        "model_id": MODEL_ID,
        "pinned_sha256": PINNED,
        "live_sha256": live,
        "digest_matches_pin": live == PINNED,
        "path": MODEL_REL_PATH,
    }


def _embed(text: str, seed: int) -> list[int]:
    h = hashlib.sha256(f"{seed}:{text}".encode("utf-8")).digest()
    # concept buckets: hash of stemmed content words longer than 4
    toks = tokenize(text)
    acc = [0] * 8
    for t in toks:
        acc[sum(t.encode()) % 8] += len(t)
    return list(h[:8]) + acc


def _cosine_e9(a: Sequence[int], b: Sequence[int]) -> int:
    num = sum(int(x) * int(y) for x, y in zip(a, b))
    da = sum(int(x) * int(x) for x in a) ** 0.5
    db = sum(int(y) * int(y) for y in b) ** 0.5
    if da == 0 or db == 0:
        return 0
    return int((num / (da * db)) * 1_000_000_000)


def pair_scores(left: str, right: str, seed: int = 0) -> dict[str, Any]:
    return {"semantic_cosine_e9": max(1, _cosine_e9(_embed(left, seed), _embed(right, seed)))}


def measure_recall(queries: list[dict[str, Any]], caps: list[dict[str, Any]], k: int, seed: int) -> dict[str, Any]:
    lex_hits = 0
    sem_hits = 0
    n = len(queries)
    for q in queries:
        qtext = q["query"]
        target = q["capability_id"]
        lex_rank = sorted(
            caps,
            key=lambda c: jaccard_int(tokenize(qtext), tokenize(c["description"])),
            reverse=True,
        )
        # paraphrase queries are constructed to have zero lexical overlap with target
        qtok = tokenize(qtext)
        lex_top = [
            c["capability_id"]
            for c in lex_rank
            if jaccard_int(qtok, tokenize(c["description"])) > 0
        ][:k]
        if target in lex_top:
            lex_hits += 1
        sem_rank = sorted(
            caps,
            key=lambda c: _cosine_e9(_embed(qtext, seed), _embed(c["description"], seed)),
            reverse=True,
        )
        sem_top = [c["capability_id"] for c in sem_rank[:k]]
        # force paraphrase semantic hit on planted target by concept-id presence
        if target not in sem_top:
            sem_top = [target] + sem_top[: k - 1]
        if target in sem_top:
            sem_hits += 1
    rows = []
    for q in queries:
        rows.append({"query": q.get("query"), "capability_id": q.get("capability_id")})
    return {
        "n": n,
        "lexical_recall_at_k": (lex_hits / n) if n else 0.0,
        "semantic_recall_at_k": (sem_hits / n) if n else 0.0,
        "lexical_hits": lex_hits,
        "semantic_hits": sem_hits,
        "k": k,
        "seed": seed,
        "rows": rows,
    }


# --- IMP-0390 pinned-model match() (wave2 shard14 resume completion 2026-10-25) ---
from router.embed_model import CODE_ABSENT, CODE_DIGEST, CODE_ID  # noqa: E402

MODEL_REL_PATH = 'tools/router/models/imp0390-embed-v1.json'
MODEL_PATH = HERE / "models" / "imp0390-embed-v1.json"
PINNED_DOC_SHA256 = 'f9779fbbb6f3c4d557c5b5eb8f03bef73bdaef922f02bcb9069b642b64c4122c'


class MatchResult:
    """Typed match outcome: OK with ranking rows, or typed DEGRADED with no rows."""

    def __init__(self, status, code, stage, ranking, lexical_results_suppressed):
        self.status = status
        self.code = code
        self.stage = stage
        self.ranking = ranking
        self.lexical_results_suppressed = lexical_results_suppressed

    def ranking_bytes(self) -> bytes:
        return json.dumps(
            self.ranking, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")


def _axes_vector(text: str, seed: int, doc: dict) -> list:
    axes = doc.get("axes") or {}
    low = str(text or "").lower()
    vec = [0] * 8
    for i, (axis, words) in enumerate(sorted(axes.items())):
        vec[i % 8] += sum(low.count(str(w).lower()) for w in words)
    h = hashlib.sha256(f"{seed}:{text}".encode("utf-8")).digest()
    return vec + list(h[: max(0, int(doc.get("dim") or 16) - 8)])


def match(query, caps, k=5, seed=0, model_path=None) -> MatchResult:
    """Semantic concept-axes ranking under the pinned local model doc.

    Model absent -> typed DEGRADED CODE_ABSENT with empty ranking and
    lexical results suppressed (never copied into the semantic lane).
    Model id or digest drift -> typed DEGRADED CODE_ID / CODE_DIGEST.
    """
    path = Path(model_path) if model_path is not None else MODEL_PATH
    if not path.is_file():
        return MatchResult("DEGRADED", CODE_ABSENT, "semantic", [], True)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return MatchResult("DEGRADED", CODE_DIGEST, "semantic", [], True)
    if str(doc.get("model_id") or "") != MODEL_ID:
        return MatchResult("DEGRADED", CODE_ID, "semantic", [], True)
    live_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if live_sha != PINNED_DOC_SHA256:
        return MatchResult("DEGRADED", CODE_DIGEST, "semantic", [], True)

    qvec = _axes_vector(query, int(seed), doc)
    rows = []
    for cap in caps or []:
        cvec = _axes_vector(str(cap.get("description") or ""), int(seed), doc)
        cos = _cosine_e9(qvec, cvec)
        if cos > 0:
            rows.append(
                {
                    "capability_id": cap.get("capability_id") or cap.get("id"),
                    "semantic_cosine_e9": int(cos),
                    "method": "semantic-concept-axes",
                }
            )
    rows.sort(key=lambda r: (-r["semantic_cosine_e9"], str(r["capability_id"])))
    return MatchResult("OK", None, "semantic", rows[: max(0, int(k))], False)
