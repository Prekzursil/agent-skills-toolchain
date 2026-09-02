"""Token Jaccard (lexical) and hashed n-gram cosine (embedding) detectors.

Mechanically different:
  * lexical  — unordered word-token set overlap, no synonym expansion
  * embedding — signed feature-hash of synonym-normalized tokens plus
    character 3-grams into a dense vector, then cosine similarity

A neural embedding model is ABSENT on this worktree. The second detector is
the hashing trick (a real embedding, not a second Jaccard). A full rewrite
of the same mechanism still lands in the distinct band; that coverage gap
must be disclosed, never papered over.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "for",
    "in",
    "on",
    "with",
    "by",
    "is",
    "are",
    "be",
    "was",
    "were",
    "been",
    "being",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "as",
    "at",
    "from",
    "into",
    "than",
    "then",
    "so",
    "not",
    "no",
    "nor",
    "but",
    "if",
    "we",
    "they",
    "has",
    "have",
    "had",
    "do",
    "does",
    "did",
    "must",
    "get",
    "gets",
    "a",
}

# Embedding-only synonym fold. Lexical Jaccard never sees this table.
SYNONYMS = {
    "verify": "check",
    "verifies": "check",
    "verified": "check",
    "recheck": "check",
    "rechecked": "check",
    "confirm": "check",
    "confirms": "check",
    "confirmation": "check",
    "writing": "write",
    "written": "write",
    "emitted": "write",
    "emitting": "write",
    "completion": "final",
    "wrap": "final",
    "agent": "actor",
    "assembler": "actor",
    "document": "report",
    "covers": "includes",
    "digest": "hash",
    "populated": "nonempty",
    "empty": "nonempty",
    "byte": "size",
    "bytes": "size",
    "floor": "minimum",
    "contract": "schema",
    "parse": "schema",
    "parses": "schema",
    "listed": "manifest",
    "files": "artifact",
    "file": "artifact",
    "fifteen": "five",
}


def tokens(text: str) -> list[str]:
    out: list[str] = []
    for raw in TOKEN_RE.findall((text or "").lower()):
        if raw in STOP or len(raw) < 2:
            continue
        out.append(raw)
    return out


def token_set(text: str) -> set[str]:
    return set(tokens(text))


def jaccard(a: str, b: str) -> float:
    sa, sb = token_set(a), token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _fold(tok: str) -> str:
    return SYNONYMS.get(tok, tok)


def _signed_index(prefix: bytes, payload: str, dim: int) -> tuple[int, float]:
    digest = hashlib.sha256(prefix + payload.encode("utf-8")).digest()
    idx = int.from_bytes(digest[:2], "big") % dim
    sign = 1.0 if digest[2] & 1 == 0 else -1.0
    return idx, sign


def embed(text: str, dim: int) -> tuple[float, ...]:
    folded = [_fold(t) for t in tokens(text)]
    vec = [0.0] * dim
    for tok in folded:
        idx, sign = _signed_index(b"tok:", tok, dim)
        vec[idx] += sign
    joined = " ".join(folded)
    for i in range(max(0, len(joined) - 2)):
        ng = joined[i : i + 3]
        idx, sign = _signed_index(b"c3:", ng, dim)
        vec[idx] += 0.5 * sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return tuple(x / norm for x in vec)


def cosine(left: Iterable[float], right: Iterable[float]) -> float:
    acc = 0.0
    n = 0
    for a, b in zip(left, right):
        acc += a * b
        n += 1
    if n == 0:
        return 0.0
    if acc < 0.0:
        return 0.0
    if acc > 1.0:
        return 1.0
    return acc
