"""Two mechanically different body-level detectors for AUD-0069.

Probe 1 uses token-set Jaccard (unstemmed, stopwords kept). Probe 2 uses
cosine over stemmed content-word term frequencies. A full rewrite of the
same mechanism lands in the DISTINCT band for both — that coverage limit is
disclosed, not papered over with a third threshold.
"""
from __future__ import annotations

import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    "the a an to of and or for in on at as it that this when whenever besides "
    "beside next into from with without by be is are was were so same".split()
)
STEM_SUFFIXES = (
    "ing",
    "ers",
    "ies",
    "tion",
    "sion",
    "ment",
    "ness",
    "ally",
    "ed",
    "es",
    "er",
    "ly",
    "s",
)

# Rename / exact-body band.
JAC_RENAME = 0.95
# Lexical candidate band (paraphrase is designed to sit below this).
JAC_CANDIDATE = 0.50
# Embedding duplicate band (paraphrase is designed to sit above this).
EMB_DUP = 0.50


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def stem(word: str) -> str:
    w = word
    for suf in STEM_SUFFIXES:
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def jaccard(a: str, b: str) -> float:
    """Lexical near-duplicate: unstemmed token-set Jaccard, stopwords kept."""
    left, right = set(tokenize(a)), set(tokenize(b))
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def embedding_vector(text: str) -> Counter:
    """Stemmed content-word bag. Mechanically unlike Jaccard's unstemmed sets."""
    return Counter(stem(tok) for tok in tokenize(text) if tok not in STOP)


def cosine(left: Counter, right: Counter) -> float:
    if not left or not right:
        return 0.0
    keys = set(left) | set(right)
    dot = sum(left[k] * right[k] for k in keys)
    n1 = math.sqrt(sum(v * v for v in left.values()))
    n2 = math.sqrt(sum(v * v for v in right.values()))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return dot / (n1 * n2)


def embedding_cosine(a: str, b: str) -> float:
    return cosine(embedding_vector(a), embedding_vector(b))


def classify(jac: float, emb: float) -> str:
    if jac >= JAC_RENAME:
        return "RENAME"
    if jac < JAC_CANDIDATE and emb >= EMB_DUP:
        return "PARAPHRASE"
    if jac >= JAC_CANDIDATE:
        return "FORK-OR-NEAR"
    return "DISTINCT"


def lexical_fires(jac: float) -> bool:
    return jac >= JAC_CANDIDATE


def embedding_fires(emb: float) -> bool:
    return emb >= EMB_DUP


def score_pair(body_a: str, body_b: str) -> dict:
    jac = jaccard(body_a, body_b)
    emb = embedding_cosine(body_a, body_b)
    kind = classify(jac, emb)
    return {
        "jaccard": round(jac, 6),
        "embedding_cosine": round(emb, 6),
        "class": kind,
        "lexical_fires": lexical_fires(jac),
        "embedding_fires": embedding_fires(emb),
        "confirmed_same_mechanism": kind in {"RENAME", "PARAPHRASE"},
    }
