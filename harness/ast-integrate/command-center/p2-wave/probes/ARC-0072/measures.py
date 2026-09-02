#!/usr/bin/env python3
"""Two mechanically different similarity measures over mechanism statements.

1. Token-set Jaccard over mechanism-statement tokens (unordered unique words).
2. Signed hashed character-trigram embedding cosine (frequency-weighted
   n-grams, not a set). These disagree on order/frequency/paraphrase in
   principle; a pair is DUPLICATE only when BOTH fire.
"""
from __future__ import annotations

import hashlib
import math
import re

from extract import concatenated_text, is_identity_token

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "in",
        "on",
        "for",
        "and",
        "or",
        "is",
        "are",
        "be",
        "by",
        "with",
        "that",
        "this",
        "it",
        "as",
        "at",
        "from",
        "its",
        "their",
        "was",
        "were",
        "been",
        "being",
        "has",
        "have",
        "had",
        "do",
        "does",
        "did",
        "not",
        "no",
        "nor",
        "so",
        "if",
        "then",
        "than",
        "into",
        "over",
        "under",
        "via",
        "per",
        "vs",
        "will",
        "can",
        "must",
        "should",
        "may",
        "also",
        "only",
        "both",
        "each",
        "all",
        "any",
        "same",
        "such",
        "other",
        "own",
        "just",
        "more",
        "most",
        "very",
        "here",
        "there",
        "when",
        "where",
        "what",
        "which",
        "who",
        "how",
        "why",
        "after",
        "before",
        "between",
        "without",
        "within",
        "true",
        "false",
        "json",
        "file",
        "path",
        "role",
        "unit",
        "plus",
        "every",
        "specify",
        "define",
        "named",
        "using",
        "used",
        "into",
        "onto",
    }
)

# Near-copy bar. Distinct architectures sit well below; a renamed dossier sits well above.
JACCARD_THRESHOLD = 0.70
COSINE_THRESHOLD = 0.82
STATEMENT_MATCH = 0.80
EMBED_DIM = 256


def tokenize(text: str) -> set[str]:
    out: set[str] = set()
    for tok in TOKEN_RE.findall(text.lower()):
        if len(tok) < 3 or tok in STOP:
            continue
        if is_identity_token(tok):
            continue
        out.add(tok)
    return out


def tokens_of(arch: dict) -> set[str]:
    acc: set[str] = set()
    for row in arch.get("statements") or []:
        acc |= tokenize(row.get("text") or "")
    return acc


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def embed_text(text: str) -> list[float]:
    vec = [0.0] * EMBED_DIM
    padded = f"  {text.lower()}  "
    for i in range(len(padded) - 2):
        gram = padded[i : i + 3]
        digest = hashlib.sha256(gram.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "little") % EMBED_DIM
        sign = 1.0 if digest[2] & 1 == 0 else -1.0
        vec[idx] += sign
    return vec


def cosine(u: list[float], v: list[float]) -> float:
    num = sum(a * b for a, b in zip(u, v))
    nu = math.sqrt(sum(a * a for a in u))
    nv = math.sqrt(sum(b * b for b in v))
    if nu == 0.0 or nv == 0.0:
        return 0.0
    return num / (nu * nv)


def embedding_of(arch: dict) -> list[float]:
    return embed_text(concatenated_text(arch))


def classify(jaccard_s: float, cosine_s: float) -> str:
    j_flag = jaccard_s >= JACCARD_THRESHOLD
    c_flag = cosine_s >= COSINE_THRESHOLD
    if j_flag and c_flag:
        return "DUPLICATE"
    if j_flag or c_flag:
        return "CONTESTED"
    return "DISTINCT"


def statement_jaccard(left: str, right: str) -> float:
    return jaccard(tokenize(left), tokenize(right))


def shared_statements(left: dict, right: dict) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for a in left.get("statements") or []:
        ta = a.get("text") or ""
        best = None
        best_s = 0.0
        for b in right.get("statements") or []:
            tb = b.get("text") or ""
            s = statement_jaccard(ta, tb)
            if s > best_s:
                best_s = s
                best = tb
        if best is not None and best_s >= STATEMENT_MATCH:
            key = (ta, best)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "left": ta,
                    "right": best,
                    "statement_jaccard": round(best_s, 4),
                }
            )
    return out
