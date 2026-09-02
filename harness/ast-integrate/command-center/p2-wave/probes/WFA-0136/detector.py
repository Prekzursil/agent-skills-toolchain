"""Lexical Jaccard vs sparse TF-IDF embedding cosine for WFA-0136.

The semantic vector is an L2-normalized bag-of-weighted-terms embedding
(word TF-IDF plus a mechanism exact-id channel). Cosine on that vector is
mechanically different from token-set Jaccard: a full rewrite that keeps
the same mechanism hashes into the same exact-id dimension and scores high,
while Jaccard on the rewritten prose stays in the genuinely-distinct band.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

WORD_RE = re.compile(r"[a-z0-9]+")

# Shared WFA-catalog boilerplate. Leaving it in the bag collapses unrelated
# units that all quote the same evidence-requirement formula.
STOP = frozenset(
    """
    a an the and or of to for with from on in at by as is are was were be been being
    this that these those it its their there which who whom whose what when where why how
    not no nor but if then than so such same other another each every all any both few more
    most some only own too very can will just should now also unit units work catalog
    artifact artifacts evidence requirement requirements command center file line files
    lines path paths json md python probe probes two mechanically independent signals
    anchored rerunnable planted mutant mutants control controls detector detectors both
    states state success failed blocked vendor reviewer reviewers retry policy strikes
    pivot fingerprint fingerprints implementation target question report named must may
    never shall wfa workflow workflows blueprint blueprints
    """.split()
)

MECH_WEIGHT = 2.4
MECH_TOKEN_WEIGHT = 0.4
COS_GAP_FLOOR = 0.25
JAC_TH_DEFAULT = 0.42
WORDING_ONLY_RE = re.compile(
    r"\b(reworded|wording only|phrasing only|same words|synonym only)\b",
    re.I,
)
MECH_DIFF_RE = re.compile(
    r"(mechanism|attacks |measures |checks |defines |triggered by|repairs |"
    r"distinct|different (target|failure|detector|path|gate|query|artifact)|"
    r"not a wording|WFA-\d{4})",
    re.I,
)


def tokens(text: str) -> list[str]:
    return [
        t
        for t in WORD_RE.findall((text or "").lower())
        if t not in STOP and len(t) > 2
    ]


def jaccard(a: str, b: str) -> float:
    sa, sb = set(tokens(a)), set(tokens(b))
    if not sa and not sb:
        return 1.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def default_idf(n_docs: int) -> float:
    return math.log((n_docs + 1) / 1) + 1.0


def fit_idf(documents: Iterable[str]) -> dict[str, float]:
    docs = list(documents)
    n = len(docs)
    df: Counter[str] = Counter()
    for doc in docs:
        df.update(set(tokens(doc)))
    return {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}


def embed(text: str, mechanism: str, idf: dict[str, float], n_docs: int) -> dict[str, float]:
    vec: dict[str, float] = {}
    tf = Counter(tokens(text))
    tot = sum(tf.values()) or 1
    fallback = default_idf(n_docs)
    for term, count in tf.items():
        vec[f"w:{term}"] = (count / tot) * idf.get(term, fallback)
    mech = (mechanism or "").strip().lower()
    if mech:
        vec["ME:" + mech] = MECH_WEIGHT
        for term in tokens(mech):
            vec[f"m:{term}"] = vec.get(f"m:{term}", 0.0) + MECH_TOKEN_WEIGHT
    norm = math.sqrt(sum(x * x for x in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def cosine(u: dict[str, float], v: dict[str, float]) -> float:
    if len(u) > len(v):
        u, v = v, u
    return sum(val * v[key] for key, val in u.items() if key in v)


def calibrate_thresholds(para_cos: float, dist_cos: float, para_jac: float) -> dict:
    if para_cos <= dist_cos:
        return {
            "ok": False,
            "reason": "paraphrase cosine is not above distinct cosine",
            "paraphrase_cosine": para_cos,
            "distinct_cosine": dist_cos,
        }
    gap = para_cos - dist_cos
    if gap < COS_GAP_FLOOR:
        return {
            "ok": False,
            "reason": f"planted gap {gap:.4f} < {COS_GAP_FLOOR}",
            "paraphrase_cosine": para_cos,
            "distinct_cosine": dist_cos,
        }
    jac_th = JAC_TH_DEFAULT
    if para_jac >= jac_th:
        return {
            "ok": False,
            "reason": "planted paraphrase is not Jaccard-distinct; rewrite the plant",
            "paraphrase_jaccard": para_jac,
            "jaccard_threshold": jac_th,
        }
    cos_th = dist_cos + 0.60 * gap
    cos_th = min(cos_th, para_cos - 0.10)
    return {
        "ok": True,
        "cosine_threshold": cos_th,
        "jaccard_threshold": jac_th,
        "gap": gap,
        "rule": "distinct_cosine + 0.60 * (paraphrase_cosine - distinct_cosine), capped 0.10 below paraphrase",
    }


def semantic_flag(cosine_score: float, threshold: float) -> bool:
    return cosine_score >= threshold


def lexical_flag(jaccard_score: float, threshold: float) -> bool:
    return jaccard_score >= threshold


def nadb_kind(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return "absent"
    if WORDING_ONLY_RE.search(raw) and not MECH_DIFF_RE.search(raw):
        return "wording-only"
    if MECH_DIFF_RE.search(raw):
        return "mechanism-difference"
    return "unclassified"
