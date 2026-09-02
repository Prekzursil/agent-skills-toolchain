#!/usr/bin/env python3
"""Two mechanically different similarity measures for CNF-0078.

lexical: token-set Jaccard on surface words (author token-overlap analogue).
embedding: cosine over a fixed concept-axis vector after synonym-family hits.

The embedding is NOT a learned sentence model. It is a local concept-axis
embedding whose axes are the synonym families below. A rewrite whose
vocabulary sits outside that lexicon is invisible to it — that limit is
the measure's scope, not a hidden gap to paper over.
"""
from __future__ import annotations

import math
import re
from typing import Iterable

LEX_THRESHOLD = 0.50
EMB_THRESHOLD = 0.70

STOP = frozenset(
    """
    a an the of to and or in on at for from that this those these with without
    than rather same then into over under is be by as it its any this those
    only also not no yes do did than then them they their
    """.split()
)

# Longest phrases first inside each axis. Matching is substring on a
# space-normalized lowercase haystack, so multi-word phrases win.
AXES: list[tuple[str, list[str]]] = [
    (
        "kill_mid",
        [
            "kill a workflow",
            "abort the job",
            "halfway through a step",
            "mid-run",
        ],
    ),
    (
        "stage_edge",
        [
            "stage boundary",
            "step edge",
        ],
    ),
    (
        "durable_checkpoint",
        [
            "persist a checkpoint",
            "snapshot done work",
            "durable store",
            "savepoint",
            "checkpoint",
        ],
    ),
    (
        "resume_saved",
        [
            "resume the same inputs",
            "continue the identical payload",
            "from that checkpoint",
            "off stored progress",
        ],
    ),
    (
        "skip_replay",
        [
            "without replaying",
            "skip already-applied",
            "prior side effects",
            "already-applied mutations",
        ],
    ),
    (
        "reject_corrupt",
        [
            "refuse a corrupted",
            "reject a damaged",
            "corrupted checkpoint",
            "damaged savepoint",
            "partial run",
            "half result",
        ],
    ),
]


def normalize(text: str) -> str:
    return " " + re.sub(r"\s+", " ", text.lower()).strip() + " "


def tokens(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in raw if len(t) >= 4 and t not in STOP}


def lexical_jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def axis_vector(text: str) -> list[float]:
    hay = normalize(text)
    vec: list[float] = []
    for _axis, phrases in AXES:
        hit = 0.0
        for p in phrases:
            if p in hay:
                hit = 1.0
                break
        vec.append(hit)
    return vec


def cosine(u: Iterable[float], v: Iterable[float]) -> float:
    uu = list(u)
    vv = list(v)
    if len(uu) != len(vv):
        raise ValueError("cosine dimension mismatch")
    num = sum(a * b for a, b in zip(uu, vv))
    du = math.sqrt(sum(a * a for a in uu))
    dv = math.sqrt(sum(b * b for b in vv))
    if du == 0.0 or dv == 0.0:
        return 0.0
    return num / (du * dv)


def embedding_cosine(a: str, b: str) -> float:
    return cosine(axis_vector(a), axis_vector(b))


def score_pair(a_text: str, b_text: str) -> dict:
    lex = lexical_jaccard(a_text, b_text)
    emb = embedding_cosine(a_text, b_text)
    lex_f = lex >= LEX_THRESHOLD
    emb_f = emb >= EMB_THRESHOLD
    flagged_by = []
    if lex_f:
        flagged_by.append("lexical")
    if emb_f:
        flagged_by.append("embedding")
    return {
        "lexical_score": round(lex, 6),
        "embedding_score": round(emb, 6),
        "lexical_fired": lex_f,
        "embedding_fired": emb_f,
        "flagged_by": flagged_by,
        "flagged": bool(flagged_by),
    }


