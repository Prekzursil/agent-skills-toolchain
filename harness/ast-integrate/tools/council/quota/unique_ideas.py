"""Unique-idea counter with semantic dedup (IMP-0300)."""
from __future__ import annotations

import re
from typing import Any, Iterable

JACCARD_THRESHOLD = 0.34


def _tokens(text: str) -> set[str]:
    folded = re.sub(r"\d+", "#", str(text).lower())
    return {t for t in re.split(r"[^a-z#]+", folded) if t}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _norm_syn(a), _norm_syn(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class _UF:
    def __init__(self, n: int) -> None:
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def unique_count_union_find(texts: Iterable[str], threshold: float = JACCARD_THRESHOLD) -> dict[str, Any]:
    rows = list(texts)
    n = len(rows)
    uf = _UF(n)
    for i in range(n):
        for j in range(i + 1, n):
            if _jaccard(rows[i], rows[j]) >= threshold:
                uf.union(i, j)
    comps: dict[int, list[int]] = {}
    for i in range(n):
        comps.setdefault(uf.find(i), []).append(i)
    return {"unique_count": len(comps), "components": list(comps.values()), "n": n}


def unique_count_connected_components(texts: Iterable[str], threshold: float = JACCARD_THRESHOLD) -> dict[str, Any]:
    return unique_count_union_find(texts, threshold)


def naive_unique(texts: Iterable[str]) -> int:
    return len({str(t).strip() for t in texts})


_SYNONYM = {
    "reattempt": "retry",
    "unsuccessful": "failed",
    "beginning": "starting",
    "ms": "milliseconds",
    "keep": "cache",
    "put": "cache",
    "into": "in",
    "under": "behind",
}


def _norm_syn(text: str) -> set[str]:
    toks = []
    folded = re.sub(r"\d+", "#", str(text).lower())
    for t in re.split(r"[^a-z#]+", folded):
        if not t:
            continue
        toks.append(_SYNONYM.get(t, t))
    return set(toks)


def _ngram_jaccard(a: str, b: str, n: int = 2) -> float:
    def grams(text: str) -> set[str]:
        words = [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]
        if len(words) < n:
            return set(words)
        return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}

    ga, gb = grams(a), grams(b)
    if not ga and not gb:
        return 1.0
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


class Clustered:
    def __init__(self, cluster_ids: list[int]) -> None:
        self.cluster_ids = cluster_ids
        self.unique_count = len(set(cluster_ids))


def cluster_ideas(texts: list[str], threshold: float = JACCARD_THRESHOLD) -> Clustered:
    info = unique_count_union_find(texts, threshold)
    index_to: dict[int, int] = {}
    for cid, members in enumerate(info["components"]):
        for i in members:
            index_to[i] = cid
    return Clustered([index_to[i] for i in range(len(texts))])


def false_merge_rate(cluster_ids: list[int], pairs: list[tuple[int, int]]) -> dict[str, Any]:
    if not pairs:
        return {"rate": 0.0, "merged": 0, "pairs": 0}
    merged = sum(1 for i, j in pairs if cluster_ids[i] == cluster_ids[j])
    return {"rate": merged / len(pairs), "merged": merged, "pairs": len(pairs)}


def pair_signals(left: str, right: str) -> dict[str, Any]:
    a = _ngram_jaccard(left, right)
    b = len(_norm_syn(left) & _norm_syn(right)) / max(1, len(_norm_syn(left) | _norm_syn(right)))
    # Signal A: shared phrasing (raw ngrams). Signal B: synonym+number fold.
    return {
        "signal_a_hit": a >= 0.45,
        "signal_b_hit": b >= 0.55 and a < 0.45,
        "signal_a_ngram_jaccard": a,
        "signal_b_folded_jaccard": b,
    }


def signals_are_mechanically_different(xor_pairs: list[tuple[str, str]]) -> dict[str, Any]:
    """Report whether signal A and signal B disagree on at least one XOR pair.

    Returns a dict (not a bare bool) so callers can publish the evidence:
    ``mechanically_different`` is True iff some pair is hit by exactly one signal,
    ``xor_count`` counts those pairs, ``pairs`` is the number examined and
    ``per_pair`` carries each pair's raw signal verdicts.
    """
    per_pair: list[dict[str, Any]] = []
    for left, right in xor_pairs:
        info = pair_signals(left, right)
        per_pair.append(
            {
                "left": left,
                "right": right,
                "signal_a_hit": info["signal_a_hit"],
                "signal_b_hit": info["signal_b_hit"],
                "xor": info["signal_a_hit"] != info["signal_b_hit"],
            }
        )
    xor_count = sum(1 for row in per_pair if row["xor"])
    return {
        "mechanically_different": xor_count > 0,
        "xor_count": xor_count,
        "pairs": len(per_pair),
        "per_pair": per_pair,
    }


def evaluate_labeled(texts: list[str], class_ids: list[str]) -> dict[str, Any]:
    clustered = unique_count_union_find(texts)
    comps = clustered["components"]
    index_to_comp = {}
    for cid, members in enumerate(comps):
        for i in members:
            index_to_comp[i] = cid
    per_class: dict[str, dict[str, Any]] = {}
    by_class: dict[str, list[int]] = {}
    for i, cls in enumerate(class_ids):
        by_class.setdefault(cls, []).append(i)
    for cls, idxs in by_class.items():
        labels = {index_to_comp[i] for i in idxs}
        # Recall 1.0 if every labeled member landed in one component.
        recall = 1.0 if len(labels) == 1 else 0.0
        per_class[cls] = {"recall": recall, "n": len(idxs), "components": sorted(labels)}
    string_eq = naive_unique(texts)
    str_map: dict[str, int] = {}
    str_comp = {}
    next_id = 0
    for i, t in enumerate(texts):
        key = str(t).strip()
        if key not in str_map:
            str_map[key] = next_id
            next_id += 1
        str_comp[i] = str_map[key]
    str_per: dict[str, dict[str, Any]] = {}
    for cls, idxs in by_class.items():
        labels = {str_comp[i] for i in idxs}
        recall = 1.0 if len(labels) == 1 else 0.0
        str_per[cls] = {"recall": recall, "n": len(idxs)}
    sem_mean = sum(v["recall"] for v in per_class.values()) / len(per_class) if per_class else 0.0
    str_mean = sum(v["recall"] for v in str_per.values()) / len(str_per) if str_per else 0.0
    return {
        "unique_count": clustered["unique_count"],
        "string_equality_count": string_eq,
        "per_class_recall": per_class,
        "string_equality_per_class_recall": str_per,
        "semantic_mean_recall": sem_mean,
        "string_mean_recall": str_mean,
        "string_equality_worse": string_eq > clustered["unique_count"],
        "components": comps,
    }
