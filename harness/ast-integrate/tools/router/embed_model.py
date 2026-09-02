"""Pinned local concept-embedding model for semantic capability matching (IMP-0390).

The semantic matcher must run offline and deterministically, so the "model" is
a small feature-hashing embedder whose parameters live in a JSON document:

* ``model_id``, ``version`` and ``dim`` identify the model; ``seed`` salts the
  feature hash so two models with the same lexicon but different seeds embed
  differently (and therefore carry different digests).
* ``concepts`` map a frozen concept axis to the surface tokens that express it,
  so a paraphrase ("assemble a single lookup table") and its target ("crawls the
  roots into one index") land on shared ``concept:`` features that a token
  Jaccard cannot see.  Surface stems are hashed as ``tok:`` features too, which
  is what makes verbatim text embed to cosine 1.0.
* ``weights`` give the feature weights per family (``concept`` vs ``token``).
* ``digest`` is the sha256 of the canonical document without the digest field.

Loading is *typed*: a missing file, a wrong id, or a digest that does not match
the pin all produce a ``DEGRADED`` :class:`ModelLoad` carrying one of the
``CODE_*`` constants.  Callers must not fall back to lexical ranking silently;
they report the code and suppress semantic results instead
(see :mod:`router.semantic_matcher`).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MODEL_SCHEMA = "ast.router.embed-model/v1"
MODEL_ID = "imp0390-local-concept-embed-v1.0.0"
MODEL_VERSION = "1.0.0"
ALGO = "frozen-concept-axes+token-lexicon"
DEFAULT_DIM = 256
DEFAULT_SEED = 390
DEFAULT_WEIGHTS: Mapping[str, float] = {"concept": 2.0, "token": 1.0}
MIN_DIM = 8

STATUS_OK = "OK"
STATUS_DEGRADED = "DEGRADED"

CODE_OK = "SEMANTIC-OK"
CODE_ABSENT = "PINNED-MODEL-ABSENT"
CODE_DIGEST = "PINNED-MODEL-DIGEST-MISMATCH"
CODE_ID = "PINNED-MODEL-ID-MISMATCH"
CODE_SCHEMA = "PINNED-MODEL-SCHEMA-INVALID"

E9 = 1_000_000_000

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "the",
        "of",
        "for",
        "to",
        "in",
        "on",
        "by",
        "with",
        "this",
        "that",
        "it",
        "its",
        "is",
        "are",
        "be",
        "as",
        "at",
        "or",
        "from",
        "do",
        "not",
        "use",
        "when",
        "user",
        "asks",
    }
)
_SUFFIXES = ("ing", "ers", "er", "ed", "es", "s")


class EmbedModelError(ValueError):
    """The model document is malformed."""


def tokenize(text: str) -> list[str]:
    """Lower-cased alphanumeric tokens with stop words removed (order kept)."""
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP]


def _stem(token: str) -> str:
    """Crude suffix stripping so ``reads``/``reading``/``read`` share a feature."""
    for suffix in _SUFFIXES:
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _feature_index(feature: str, seed: int, dim: int) -> tuple[int, float]:
    digest = hashlib.sha256(f"{seed}:{feature}".encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], "big") % dim
    sign = 1.0 if digest[4] & 1 else -1.0
    return index, sign


@dataclass(frozen=True)
class EmbedModel:
    """Deterministic feature-hashing embedder with a frozen concept lexicon."""

    model_id: str
    dim: int
    seed: int
    concepts: Mapping[str, tuple[str, ...]]
    token_to_concepts: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    concept_weight: float = DEFAULT_WEIGHTS["concept"]
    token_weight: float = DEFAULT_WEIGHTS["token"]
    version: str = MODEL_VERSION

    @classmethod
    def from_document(cls, doc: Mapping[str, Any]) -> "EmbedModel":
        validate_document(doc)
        concepts = {
            str(name): tuple(_stem(t) for t in tokenize(" ".join(map(str, members))))
            for name, members in dict(doc["concepts"]).items()
        }
        index: dict[str, set[str]] = {}
        for name, members in concepts.items():
            for tok in members:
                index.setdefault(tok, set()).add(name)
        weights = dict(DEFAULT_WEIGHTS)
        weights.update({str(k): float(v) for k, v in dict(doc.get("weights") or {}).items()})
        return cls(
            model_id=str(doc["model_id"]),
            dim=int(doc["dim"]),
            seed=int(doc["seed"]),
            concepts=concepts,
            token_to_concepts={k: tuple(sorted(v)) for k, v in index.items()},
            concept_weight=weights["concept"],
            token_weight=weights["token"],
            version=str(doc.get("version") or MODEL_VERSION),
        )

    def stems(self, text: str) -> list[str]:
        """Stemmed content tokens of ``text`` in order of appearance."""
        return [_stem(tok) for tok in tokenize(text)]

    def concepts_of(self, text: str) -> list[str]:
        """Sorted, de-duplicated concept axes activated by ``text``."""
        found: set[str] = set()
        for stem in self.stems(text):
            found.update(self.token_to_concepts.get(stem, ()))
        return sorted(found)

    def features(self, text: str) -> list[tuple[str, float]]:
        """Weighted features: one ``tok:`` per stem, one ``concept:`` per activation."""
        out: list[tuple[str, float]] = []
        for stem in self.stems(text):
            out.append((f"tok:{stem}", self.token_weight))
            for concept in self.token_to_concepts.get(stem, ()):
                out.append((f"concept:{concept}", self.concept_weight))
        return out

    def embed(self, text: str) -> list[float]:
        """Unit-norm vector of ``dim`` floats; the zero vector for empty text."""
        vec = [0.0] * self.dim
        for feature, weight in self.features(text):
            idx, sign = _feature_index(feature, self.seed, self.dim)
            vec[idx] += sign * weight
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]

    def similarity_e9(self, a: str, b: str) -> int:
        """Integer cosine (scaled by 1e9) between the embeddings of two texts."""
        return cosine_e9(self.embed(a), self.embed(b))


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two vectors (0.0 when either is the zero vector)."""
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch {len(a)} != {len(b)}")
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    if da == 0.0 or db == 0.0:
        return 0.0
    return max(-1.0, min(1.0, num / (da * db)))


def cosine_e9(a: Sequence[float], b: Sequence[float]) -> int:
    """Cosine scaled to an integer in [-1e9, 1e9] for byte-stable receipts."""
    return int(round(cosine(a, b) * E9))


# ------------------------------------------------------------------ documents


def canonical_bytes(doc: Mapping[str, Any]) -> bytes:
    """Canonical JSON of ``doc`` without its ``digest`` field."""
    body = {k: v for k, v in doc.items() if k != "digest"}
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def model_digest(doc: Mapping[str, Any]) -> str:
    """sha256 over the canonical document (digest field excluded)."""
    return hashlib.sha256(canonical_bytes(doc)).hexdigest()


def file_digest(path: Path | str) -> str:
    """sha256 over the file bytes with CRLF normalised to LF (manifest convention)."""
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def validate_document(doc: Any) -> None:
    """Raise :class:`EmbedModelError` unless ``doc`` is a well-formed model."""
    if not isinstance(doc, Mapping):
        raise EmbedModelError("model document must be a JSON object")
    if doc.get("schema") != MODEL_SCHEMA:
        raise EmbedModelError(f"model schema {doc.get('schema')!r} != {MODEL_SCHEMA!r}")
    if not isinstance(doc.get("model_id"), str) or not doc["model_id"]:
        raise EmbedModelError("model_id must be a non-empty string")
    version = doc.get("version", MODEL_VERSION)
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise EmbedModelError(f"version must be MAJOR.MINOR.PATCH, got {version!r}")
    dim = doc.get("dim")
    if not isinstance(dim, int) or isinstance(dim, bool) or dim < MIN_DIM:
        raise EmbedModelError(f"dim must be an integer >= {MIN_DIM}")
    seed = doc.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise EmbedModelError("seed must be an integer")
    concepts = doc.get("concepts")
    if not isinstance(concepts, Mapping) or not concepts:
        raise EmbedModelError("concepts must be a non-empty object")
    for name, members in concepts.items():
        if not isinstance(name, str) or not name:
            raise EmbedModelError("concept names must be non-empty strings")
        if (
            not isinstance(members, list)
            or not members
            or not all(isinstance(m, str) and m for m in members)
        ):
            raise EmbedModelError(f"concept {name!r} must list non-empty string members")
    weights = doc.get("weights", DEFAULT_WEIGHTS)
    if not isinstance(weights, Mapping) or set(weights) != set(DEFAULT_WEIGHTS):
        raise EmbedModelError("weights must be an object with keys concept and token")
    for key, value in weights.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise EmbedModelError(f"weight {key!r} must be a positive number")


def build_document(
    concepts: Mapping[str, Iterable[str]],
    *,
    model_id: str = MODEL_ID,
    version: str = MODEL_VERSION,
    dim: int = DEFAULT_DIM,
    seed: int = DEFAULT_SEED,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
) -> dict[str, Any]:
    """Assemble and digest a model document from a concept lexicon."""
    doc: dict[str, Any] = {
        "schema": MODEL_SCHEMA,
        "model_id": model_id,
        "version": version,
        "algo": ALGO,
        "dim": int(dim),
        "seed": int(seed),
        "weights": {str(k): float(v) for k, v in sorted(weights.items())},
        "concepts": {
            str(k): sorted({str(m) for m in v}) for k, v in sorted(concepts.items())
        },
    }
    validate_document(doc)
    doc["digest"] = model_digest(doc)
    return doc


def document_bytes(doc: Mapping[str, Any]) -> bytes:
    """The exact bytes :func:`write_model` persists for ``doc``."""
    return (json.dumps(dict(doc), indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_model(path: Path | str, doc: Mapping[str, Any]) -> Path:
    """Persist a validated, digested model document."""
    validate_document(doc)
    if doc.get("digest") != model_digest(doc):
        raise EmbedModelError("document digest does not match its content")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(document_bytes(doc))
    return target


@dataclass(frozen=True)
class ModelLoad:
    """Typed outcome of :func:`load_model`."""

    status: str
    code: str
    path: str
    model: EmbedModel | None = None
    digest: str | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK and self.model is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "code": self.code,
            "path": self.path,
            "digest": self.digest,
            "model_id": self.model.model_id if self.model else None,
            "detail": self.detail,
        }


def load_model(
    path: Path | str,
    *,
    expected_id: str = MODEL_ID,
    pinned_digest: str | None = None,
    pinned_file_sha256: str | None = None,
) -> ModelLoad:
    """Load a model, degrading with a typed code instead of raising.

    Absent file -> ``CODE_ABSENT``; unparsable/invalid -> ``CODE_SCHEMA``;
    ``model_id`` != ``expected_id`` -> ``CODE_ID``; recomputed digest != the
    document's own digest, != ``pinned_digest``, or file bytes !=
    ``pinned_file_sha256`` -> ``CODE_DIGEST``.
    """
    p = Path(path)
    if not p.is_file():
        return ModelLoad(
            STATUS_DEGRADED, CODE_ABSENT, str(p), detail="model file not found"
        )
    try:
        raw = p.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return ModelLoad(
            STATUS_DEGRADED, CODE_SCHEMA, str(p), detail=f"{type(exc).__name__}: {exc}"
        )
    try:
        validate_document(doc)
    except EmbedModelError as exc:
        return ModelLoad(STATUS_DEGRADED, CODE_SCHEMA, str(p), detail=str(exc))
    live_digest = model_digest(doc)
    if doc.get("model_id") != expected_id:
        return ModelLoad(
            STATUS_DEGRADED,
            CODE_ID,
            str(p),
            digest=live_digest,
            detail=f"model_id {doc.get('model_id')!r} != pinned {expected_id!r}",
        )
    declared = doc.get("digest")
    if declared is not None and declared != live_digest:
        return ModelLoad(
            STATUS_DEGRADED,
            CODE_DIGEST,
            str(p),
            digest=live_digest,
            detail="document digest field does not match its content",
        )
    if pinned_digest is not None and live_digest != pinned_digest:
        return ModelLoad(
            STATUS_DEGRADED,
            CODE_DIGEST,
            str(p),
            digest=live_digest,
            detail=f"digest {live_digest[:12]} != pinned {pinned_digest[:12]}",
        )
    if pinned_file_sha256 is not None:
        live_file = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        if live_file != pinned_file_sha256:
            return ModelLoad(
                STATUS_DEGRADED,
                CODE_DIGEST,
                str(p),
                digest=live_digest,
                detail=f"file sha256 {live_file[:12]} != pinned {pinned_file_sha256[:12]}",
            )
    return ModelLoad(
        STATUS_OK,
        CODE_OK,
        str(p),
        model=EmbedModel.from_document(doc),
        digest=live_digest,
    )


__all__ = [
    "ALGO",
    "CODE_ABSENT",
    "CODE_DIGEST",
    "CODE_ID",
    "CODE_OK",
    "CODE_SCHEMA",
    "DEFAULT_DIM",
    "DEFAULT_SEED",
    "DEFAULT_WEIGHTS",
    "E9",
    "EmbedModel",
    "EmbedModelError",
    "MODEL_ID",
    "MODEL_SCHEMA",
    "MODEL_VERSION",
    "ModelLoad",
    "STATUS_DEGRADED",
    "STATUS_OK",
    "build_document",
    "canonical_bytes",
    "cosine",
    "cosine_e9",
    "document_bytes",
    "file_digest",
    "load_model",
    "model_digest",
    "tokenize",
    "validate_document",
    "write_model",
]
