#!/usr/bin/env python3
"""Normalized work-unit fingerprint (IMP-0412).

Fingerprint = SHA-256 of (normalized input-set + sorted unique target tokens).
Two units collide when they share an input-set AND their target-token Jaccard
is >= JACCARD_THRESHOLD. That catches exact clones and light rewordings of the
same mechanism without collapsing thematically related but distinct units
that happen to share vocabulary (failure class: fingerprint-too-coarse).

Claim-time use: check_claim() walks the catalog (n≈2e3 is cheap) and returns
every other id that collides with the unit being acquired.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

ALGORITHM_ID = "imp-0412-target-tokens-plus-input-set-v1"
JACCARD_THRESHOLD = 0.85
TOO_COARSE_FLAGGED_FRACTION = 0.02
TOO_COARSE_MAX_CLUSTER = 12

# Conservative English fillers. Domain words (unit, work, target, catalog,
# fingerprint, claim) are kept: they are the mechanism, not noise.
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "and",
        "or",
        "in",
        "on",
        "for",
        "with",
        "by",
        "from",
        "as",
        "at",
        "is",
        "are",
        "be",
        "been",
        "being",
        "was",
        "were",
        "am",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "into",
        "over",
        "under",
        "than",
        "then",
        "so",
        "if",
        "not",
        "no",
        "yes",
        "must",
        "may",
        "can",
        "should",
        "shall",
        "will",
        "would",
        "could",
        "do",
        "does",
        "did",
        "has",
        "have",
        "had",
        "each",
        "every",
        "all",
        "any",
        "both",
        "more",
        "most",
        "other",
        "such",
        "only",
        "own",
        "same",
        "too",
        "very",
        "one",
        "two",
        "three",
        "via",
        "per",
        "versus",
        "using",
        "use",
        "used",
        "within",
        "without",
        "between",
        "their",
        "there",
        "they",
        "them",
        "we",
        "our",
        "you",
        "your",
        "also",
        "but",
        "however",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "what",
        "how",
        "why",
        "whether",
        "while",
        "after",
        "before",
        "about",
        "against",
        "among",
        "across",
        "through",
        "during",
        "including",
        "because",
        "until",
        "once",
        "just",
        "already",
        "still",
        "even",
        "ever",
        "never",
        "always",
        "here",
        "out",
        "up",
        "down",
        "off",
        "again",
        "plus",
        "together",
        "along",
        "toward",
        "towards",
        "onto",
        "upon",
        "among",
        "amongst",
    }
)

# Rewordings the planted-duplicate control is allowed to use. Keep this map
# small: a large synonym table is how a fingerprint starts flagging everything.
SYNONYMS = {
    "implement": "impl",
    "implementation": "impl",
    "write": "impl",
    "author": "impl",
    "create": "impl",
    "build": "impl",
    "normalised": "normal",
    "normalized": "normal",
    "normalise": "normal",
    "normalize": "normal",
    "ids": "id",
    "identifier": "id",
    "identifiers": "id",
    "duplicate": "dup",
    "duplicates": "dup",
    "duplicated": "dup",
    "duplication": "dup",
    "fingerprint": "fp",
    "fingerprints": "fp",
    "fingerprinted": "fp",
    "fingerprinting": "fp",
    "collide": "collision",
    "collides": "collision",
    "collided": "collision",
    "colliding": "collision",
    "collisions": "collision",
    "catalogue": "catalog",
    "catalogs": "catalog",
    "catalogues": "catalog",
    "exact": "precise",
    "precisely": "precise",
}

_STEM_SUFFIXES = (
    "ingly",
    "edly",
    "ation",
    "tions",
    "tion",
    "ments",
    "ment",
    "ness",
    "ings",
    "ing",
    "ies",
    "ied",
    "ers",
    "er",
    "est",
    "ly",
    "ed",
    "es",
    "s",
)

_LINE_RANGE = re.compile(r":\d+(-\d+)?\b")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def stem(word: str) -> str:
    for suf in _STEM_SUFFIXES:
        if len(word) > len(suf) + 3 and word.endswith(suf):
            return word[: -len(suf)]
    return word


def target_text(unit: Mapping[str, Any]) -> str:
    for key in ("question_or_target", "target", "title"):
        val = unit.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def normalize_target_tokens(text: str) -> frozenset[str]:
    folded = unicodedata.normalize("NFKC", text or "").lower()
    folded = _NON_ALNUM.sub(" ", folded)
    out: set[str] = set()
    for raw in folded.split():
        if raw in STOPWORDS or len(raw) <= 1:
            continue
        word = SYNONYMS.get(raw, raw)
        word = stem(word)
        word = SYNONYMS.get(word, word)
        if word in STOPWORDS or len(word) <= 1:
            continue
        out.add(word)
    return frozenset(out)


def normalize_input(item: Any) -> str:
    text = unicodedata.normalize("NFKC", str(item)).strip()
    text = text.replace("\\", "/").lower()
    text = _LINE_RANGE.sub("", text)
    text = text.replace("#", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_input_set(inputs: Iterable[Any] | None) -> tuple[str, ...]:
    seen: set[str] = set()
    for item in inputs or []:
        norm = normalize_input(item)
        if norm:
            seen.add(norm)
    return tuple(sorted(seen))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = len(a | b)
    if union == 0:
        return 1.0
    return len(a & b) / union


def _sha256_text(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_fingerprint(tokens: frozenset[str], inputs: Sequence[str]) -> str:
    payload = (
        ALGORITHM_ID
        + "\nI:"
        + "\n".join(inputs)
        + "\nT:"
        + " ".join(sorted(tokens))
    )
    return _sha256_text(payload)


def shared_fingerprint(
    tokens_a: frozenset[str], tokens_b: frozenset[str], inputs: Sequence[str]
) -> str:
    payload = (
        ALGORITHM_ID
        + "+shared\nI:"
        + "\n".join(inputs)
        + "\nX:"
        + " ".join(sorted(tokens_a & tokens_b))
    )
    return _sha256_text(payload)


@dataclass(frozen=True)
class FingerprintParts:
    unit_id: str
    tokens: frozenset[str]
    inputs: tuple[str, ...]
    canonical: str

    @property
    def input_key(self) -> tuple[str, ...]:
        return self.inputs


def fingerprint_parts(unit: Mapping[str, Any]) -> FingerprintParts:
    uid = str(unit.get("id") or "")
    tokens = normalize_target_tokens(target_text(unit))
    inputs = normalize_input_set(unit.get("inputs"))
    return FingerprintParts(
        unit_id=uid,
        tokens=tokens,
        inputs=inputs,
        canonical=canonical_fingerprint(tokens, inputs),
    )


def pair_collides(a: FingerprintParts, b: FingerprintParts) -> bool:
    if a.unit_id == b.unit_id:
        return False
    if a.inputs != b.inputs:
        return False
    return jaccard(a.tokens, b.tokens) >= JACCARD_THRESHOLD


def collide_pair(a: FingerprintParts, b: FingerprintParts) -> dict[str, Any] | None:
    if not pair_collides(a, b):
        return None
    left, right = sorted([a.unit_id, b.unit_id])
    parts = {a.unit_id: a, b.unit_id: b}
    pa, pb = parts[left], parts[right]
    score = jaccard(pa.tokens, pb.tokens)
    return {
        "unit_id_a": left,
        "unit_id_b": right,
        "shared_fingerprint": shared_fingerprint(pa.tokens, pb.tokens, pa.inputs),
        "canonical_a": pa.canonical,
        "canonical_b": pb.canonical,
        "jaccard": round(score, 6),
        "token_sets_equal": pa.tokens == pb.tokens,
        "input_set_equal": True,
        "normalized_inputs": list(pa.inputs),
        "shared_tokens": sorted(pa.tokens & pb.tokens),
    }


def index_parts(units: Sequence[Mapping[str, Any]]) -> list[FingerprintParts]:
    return [fingerprint_parts(u) for u in units if isinstance(u, Mapping) and u.get("id")]


def collisions_among(parts: Sequence[FingerprintParts]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, ...], list[FingerprintParts]] = {}
    for p in parts:
        buckets.setdefault(p.inputs, []).append(p)
    found: list[dict[str, Any]] = []
    for group in buckets.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                row = collide_pair(group[i], group[j])
                if row is not None:
                    found.append(row)
    found.sort(key=lambda r: (r["unit_id_a"], r["unit_id_b"]))
    return found


def too_coarse(parts: Sequence[FingerprintParts], collisions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(parts)
    flagged: set[str] = set()
    for row in collisions:
        flagged.add(str(row["unit_id_a"]))
        flagged.add(str(row["unit_id_b"]))
    clusters: dict[str, set[str]] = {}
    for row in collisions:
        a, b = str(row["unit_id_a"]), str(row["unit_id_b"])
        fp = str(row["shared_fingerprint"])
        clusters.setdefault(fp, set()).update((a, b))
    largest = max((len(v) for v in clusters.values()), default=0)
    fraction = (len(flagged) / n) if n else 0.0
    abort = bool(n and (fraction > TOO_COARSE_FLAGGED_FRACTION or largest > TOO_COARSE_MAX_CLUSTER))
    return {
        "flagged_unit_count": len(flagged),
        "flagged_fraction": round(fraction, 6),
        "largest_cluster": largest,
        "abort": abort,
        "abort_rule": (
            f"abort if flagged_fraction>{TOO_COARSE_FLAGGED_FRACTION} "
            f"or largest_cluster>{TOO_COARSE_MAX_CLUSTER}"
        ),
    }
