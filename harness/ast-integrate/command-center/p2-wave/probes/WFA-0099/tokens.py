"""Lexical Jaccard, hashed-n-gram cosine embedding, and structural set Jaccard.

A neural embedding model is ABSENT on this worktree. The embedding detector is
the hashing trick over synonym-folded tokens plus character 3-grams — a real
vector cosine, not a second Jaccard. Lexical Jaccard never consults the
synonym table, so a paraphrase can fire embedding while missing lexical.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Iterable, Mapping

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = {
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "with", "by",
    "is", "are", "be", "was", "were", "been", "being", "this", "that", "these",
    "those", "it", "its", "as", "at", "from", "into", "than", "then", "so",
    "not", "no", "nor", "but", "if", "we", "they", "has", "have", "had", "do",
    "does", "did", "must", "get", "gets",
}

# Embedding-only synonym fold. Lexical Jaccard never sees this table.
SYNONYMS = {
    "verify": "check",
    "verifies": "check",
    "verified": "check",
    "confirm": "check",
    "confirms": "check",
    "confirmation": "check",
    "writing": "write",
    "written": "write",
    "emitted": "write",
    "emitting": "write",
    "completion": "final",
    "wrap": "final",
    "document": "report",
    "covers": "includes",
    "digest": "hash",
    "files": "artifact",
    "file": "artifact",
    "artifacts": "artifact",
    "listed": "manifest",
}

EMBED_DIM = 384
LEXICAL_THRESHOLD = 0.48
EMBEDDING_THRESHOLD = 0.58
STRUCTURAL_THRESHOLD = 0.80

STRUCTURAL_KEYS = ("stages", "roles", "gates", "tools")


def tokens(text: str) -> list[str]:
    out: list[str] = []
    for raw in TOKEN_RE.findall((text or "").lower()):
        if raw in STOP or len(raw) < 2:
            continue
        out.append(raw)
    return out


def token_set(text: str) -> set[str]:
    return set(tokens(text))


def jaccard_sets(sa: set[str], sb: set[str]) -> float:
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    union = len(sa | sb)
    return (len(sa & sb) / union) if union else 0.0


def lexical_score(a: str, b: str) -> float:
    return jaccard_sets(token_set(a), token_set(b))


def _fold(tok: str) -> str:
    return SYNONYMS.get(tok, tok)


def _signed_index(prefix: bytes, payload: str, dim: int) -> tuple[int, float]:
    digest = hashlib.sha256(prefix + payload.encode("utf-8")).digest()
    idx = int.from_bytes(digest[:2], "big") % dim
    sign = 1.0 if digest[2] & 1 == 0 else -1.0
    return idx, sign


def embed(text: str, dim: int = EMBED_DIM) -> tuple[float, ...]:
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


def embedding_score(a: str, b: str) -> float:
    return cosine(embed(a), embed(b))


def structural_set(rec: Mapping[str, Any]) -> set[str]:
    out: set[str] = set()
    for key in STRUCTURAL_KEYS:
        for item in rec.get(key) or []:
            out.add(f"{key}:{item}")
    return out


def structural_score(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    return jaccard_sets(structural_set(left), structural_set(right))


def score_pair(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    lt = str(left.get("text") or "")
    rt = str(right.get("text") or "")
    lex = lexical_score(lt, rt)
    emb = embedding_score(lt, rt)
    st = structural_score(left, right)
    fired = []
    if lex >= LEXICAL_THRESHOLD:
        fired.append("LEXICAL")
    if emb >= EMBEDDING_THRESHOLD:
        fired.append("EMBEDDING")
    if st >= STRUCTURAL_THRESHOLD:
        fired.append("STRUCTURAL")
    return {
        "lexical": round(lex, 6),
        "embedding": round(emb, 6),
        "structural": round(st, 6),
        "lexical_hit": lex >= LEXICAL_THRESHOLD,
        "embedding_hit": emb >= EMBEDDING_THRESHOLD,
        "structural_hit": st >= STRUCTURAL_THRESHOLD,
        "fired": fired,
        "thresholds": {
            "LEXICAL": LEXICAL_THRESHOLD,
            "EMBEDDING": EMBEDDING_THRESHOLD,
            "STRUCTURAL": STRUCTURAL_THRESHOLD,
        },
    }
