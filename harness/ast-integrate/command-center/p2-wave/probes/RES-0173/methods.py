#!/usr/bin/env python3
"""Three named claim-dedup methods plus two taxonomy calibrators.

Lexical Jaccard and random-index cosine are computed from claim TEXT only.
Mechanism-key equality reads the authored action|object slots and IGNORES
the parameter slot (a one-parameter fork must not mint a new mechanism).

Neural / transformer sentence-embedding cosine is not implemented here:
this worktree has no numpy, sklearn, or sentence-transformers runtime.
The cosine method below is seeded random indexing (Kanerva-style mean
pool of token sign vectors). It is an embedding cosine, not a neural one.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

JACCARD_THRESHOLD = 0.50
COSINE_THRESHOLD = 0.70
EMBED_DIM = 256
EMBED_SEED = 20260824

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "and",
        "to",
        "for",
        "in",
        "on",
        "with",
        "by",
        "or",
        "as",
        "is",
        "are",
        "that",
        "this",
        "from",
        "be",
        "it",
        "its",
        "at",
        "into",
        "over",
        "than",
        "then",
        "not",
        "no",
        "if",
        "when",
        "every",
        "must",
        "may",
        "does",
        "do",
        "did",
        "has",
        "have",
        "had",
        "was",
        "were",
        "been",
        "being",
        "also",
        "both",
        "each",
        "same",
        "one",
        "two",
        "three",
        "rather",
        "without",
        "unless",
        "remain",
        "remains",
    }
)


def tokens(text: str) -> frozenset[str]:
    raw = TOKEN_RE.findall((text or "").lower())
    return frozenset(t for t in raw if t not in STOP and len(t) > 1)


def jaccard(a: str, b: str) -> float:
    A, B = tokens(a), tokens(b)
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def _norm_slot(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def mechanism_key(claim: dict) -> str | None:
    mech = claim.get("canonical_mechanism")
    if not isinstance(mech, dict):
        return None
    action = _norm_slot(mech.get("action"))
    obj = _norm_slot(mech.get("object"))
    if not action or not obj:
        return None
    return f"{action}|{obj}"


def _token_signs(token: str, dim: int = EMBED_DIM, seed: int = EMBED_SEED) -> list[int]:
    out: list[int] = []
    block = 0
    while len(out) < dim:
        digest = hashlib.sha256(f"{seed}:{token}:{block}".encode("utf-8")).digest()
        for byte in digest:
            for bit in range(8):
                out.append(1 if ((byte >> bit) & 1) else -1)
                if len(out) == dim:
                    return out
        block += 1
    return out


def embed(text: str, dim: int = EMBED_DIM) -> list[int]:
    vec = [0] * dim
    toks = tokens(text)
    if not toks:
        return vec
    for tok in toks:
        signs = _token_signs(tok, dim=dim)
        for i, s in enumerate(signs):
            vec[i] += s
    return vec


def cosine(a: str, b: str) -> float:
    u, v = embed(a), embed(b)
    dot = 0
    nu = 0
    nv = 0
    for x, y in zip(u, v):
        dot += x * y
        nu += x * x
        nv += y * y
    if nu == 0 or nv == 0:
        return 1.0 if nu == 0 and nv == 0 else 0.0
    return dot / (math.sqrt(nu) * math.sqrt(nv))


def merge_jaccard(a: str, b: str, threshold: float = JACCARD_THRESHOLD) -> bool:
    return jaccard(a, b) >= threshold


def merge_cosine(a: str, b: str, threshold: float = COSINE_THRESHOLD) -> bool:
    return cosine(a, b) >= threshold


def merge_mechanism(left: dict, right: dict) -> bool:
    k1, k2 = mechanism_key(left), mechanism_key(right)
    return k1 is not None and k1 == k2


def merge_exact_string(a: str, b: str) -> bool:
    return (a or "").strip() == (b or "").strip()


def merge_always(_a: str, _b: str) -> bool:
    return True


def pairwise_named(left: dict, right: dict) -> dict:
    t1 = left.get("text") or ""
    t2 = right.get("text") or ""
    jac = round(jaccard(t1, t2), 6)
    cos = round(cosine(t1, t2), 6)
    k1, k2 = mechanism_key(left), mechanism_key(right)
    return {
        "left": left["id"],
        "right": right["id"],
        "jaccard": jac,
        "cosine": cos,
        "mechanism_left": k1,
        "mechanism_right": k2,
        "lexical_jaccard_merge": jac >= JACCARD_THRESHOLD,
        "embedding_cosine_merge": cos >= COSINE_THRESHOLD,
        "mechanism_key_merge": k1 is not None and k1 == k2,
        "exact_string_merge": merge_exact_string(t1, t2),
        "always_merge": True,
    }


def taxonomy(all_paraphrases_merged: bool, any_distinction_merged: bool) -> str:
    """both-states labels from tests_required.

    correct: merge every paraphrase AND keep every true distinction apart
    collapser: merge paraphrases AND merge distinctions
    string_comparator: merge neither (does not merge paraphrases; typically
    also keeps distinctions, because it barely merges anything)
    inverted: merge distinctions but miss paraphrases
    """
    if all_paraphrases_merged and not any_distinction_merged:
        return "correct"
    if all_paraphrases_merged and any_distinction_merged:
        return "collapser"
    if not all_paraphrases_merged and not any_distinction_merged:
        return "string_comparator"
    return "inverted"


def named_method_ids() -> tuple[str, ...]:
    return ("lexical_jaccard", "embedding_cosine", "mechanism_key")


def control_method_ids() -> tuple[str, ...]:
    return ("always_merge", "exact_string")


def method_merge_field(method_id: str) -> str:
    return {
        "lexical_jaccard": "lexical_jaccard_merge",
        "embedding_cosine": "embedding_cosine_merge",
        "mechanism_key": "mechanism_key_merge",
        "always_merge": "always_merge",
        "exact_string": "exact_string_merge",
    }[method_id]


def iterate_pairs(claims: list[dict]) -> Iterable[tuple[dict, dict]]:
    for i, left in enumerate(claims):
        for right in claims[i + 1 :]:
            yield left, right
