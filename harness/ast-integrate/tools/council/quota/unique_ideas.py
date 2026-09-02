"""Unique-idea counter with semantic dedup (IMP-0300).

Two mechanically different similarity signals decide whether two idea strings
are the same mechanism:

* **S1 raw Jaccard** — token-set Jaccard over the raw (lower-cased, digit-folded)
  tokens, fired at :data:`JACCARD_THRESHOLD`. Catches renames, single-word swaps
  and suffix padding ("idea 17"), where most tokens survive verbatim.
* **S2 mechanism key** — equality of :func:`mechanism_key`, the sorted set of
  content tokens after stop-word removal and synonym/stem folding. Catches a full
  in-vocabulary rewrite where S1 is blind.

Two strings are one idea when either signal fires; the unique-idea count is the
number of connected components of that relation. :func:`naive_unique` (string
equality) is evidence only — the ``unique_ideas >= floor`` stopping target may be
satisfied only by :func:`stopping_unique_count` (TST-0265).
"""
from __future__ import annotations

import re
from collections import deque
from typing import Any, Iterable

JACCARD_THRESHOLD = 0.50
UNIQUE_IDEAS_FLOOR = 100
# A corpus of genuinely distinct ideas may lose at most this fraction of its
# strings to dedup before the counter is judged to over-merge.
DISTINCT_COLLAPSE_TOLERANCE = 0.05
SIMILARITY_METHOD = "raw-token-jaccard(S1) OR folded-mechanism-key(S2); connected components"

_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "of", "to", "in", "into", "on", "at", "by",
        "for", "with", "using", "via", "through", "that", "this", "those", "these",
        "is", "are", "be", "as", "so", "its", "it", "from", "than", "then", "when",
    }
)


def _tokens(text: str) -> set[str]:
    """Every lower-cased token; runs of digits fold to ``#`` so padding suffixes
    ("... 17") add exactly one token instead of a fresh one per string."""
    folded = re.sub(r"\d+", "#", str(text).lower())
    return {t for t in re.split(r"[^a-z#]+", folded) if t}


def raw_tokens(text: str) -> set[str]:
    """Raw (un-folded) content tokens: lower-cased, digit-folded, stop-words dropped.

    Stop-words are dropped from both signals so that two distinct mechanisms that
    share only glue words ("a ... with ... and") do not reach the S1 threshold.
    """
    return {t for t in _tokens(text) if t not in _STOPWORDS}


content_tokens = raw_tokens


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """Jaccard similarity of two token sets; two empty sets are identical."""
    ta, tb = set(a), set(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _jaccard(a: str, b: str) -> float:
    return jaccard(_norm_syn(a), _norm_syn(b))


def raw_jaccard(a: str, b: str) -> float:
    return jaccard(raw_tokens(a), raw_tokens(b))


def mechanism_key(text: str) -> str:
    """Canonical mechanism key: sorted, synonym-folded content tokens (S2)."""
    toks = {_SYNONYM.get(t, t) for t in raw_tokens(text) if t not in _STOPWORDS}
    toks = {t for t in toks if t and t not in _STOPWORDS}
    return " ".join(sorted(toks))


def pair_signals_s1_s2(a: str, b: str) -> dict[str, Any]:
    j = raw_jaccard(a, b)
    keys_equal = mechanism_key(a) == mechanism_key(b)
    return {
        "raw_jaccard": j,
        "s1_fires": j >= JACCARD_THRESHOLD,
        "s2_fires": keys_equal,
        "keys_equal": keys_equal,
    }


def pair_decision(a: str, b: str) -> str:
    """``FIRE`` when the pair is one mechanism under S1 or S2, else ``SILENT``."""
    sig = pair_signals_s1_s2(a, b)
    return "FIRE" if (sig["s1_fires"] or sig["s2_fires"]) else "SILENT"


def _similar(a: str, b: str, threshold: float) -> bool:
    """Edge predicate shared by every counter in this module."""
    if raw_jaccard(a, b) >= threshold:
        return True
    if _jaccard(a, b) >= threshold:
        return True
    return mechanism_key(a) == mechanism_key(b)


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


def components_union_find(texts: Iterable[str], threshold: float = JACCARD_THRESHOLD) -> dict[str, Any]:
    """Author-side clustering (union-find). Returns the component structure."""
    rows = list(texts)
    n = len(rows)
    uf = _UF(n)
    for i in range(n):
        for j in range(i + 1, n):
            if _similar(rows[i], rows[j], threshold):
                uf.union(i, j)
    comps: dict[int, list[int]] = {}
    for i in range(n):
        comps.setdefault(uf.find(i), []).append(i)
    return {"unique_count": len(comps), "components": list(comps.values()), "n": n}


def unique_count_union_find(texts: Iterable[str], threshold: float = JACCARD_THRESHOLD) -> int:
    """Post-dedup unique-idea count (author algorithm: union-find)."""
    return int(components_union_find(texts, threshold)["unique_count"])


def unique_count_connected_components(texts: Iterable[str], threshold: float = JACCARD_THRESHOLD) -> int:
    """Independent reviewer recount: BFS over the same edge predicate, no union-find."""
    rows = list(texts)
    n = len(rows)
    seen = [False] * n
    count = 0
    for start in range(n):
        if seen[start]:
            continue
        count += 1
        seen[start] = True
        queue = deque([start])
        while queue:
            i = queue.popleft()
            for j in range(n):
                if not seen[j] and _similar(rows[i], rows[j], threshold):
                    seen[j] = True
                    queue.append(j)
    return count


def unique_count_jaccard_only(texts: Iterable[str], threshold: float = JACCARD_THRESHOLD) -> int:
    """S1-only count (raw Jaccard edges), published so S2's contribution is visible."""
    rows = list(texts)
    n = len(rows)
    uf = _UF(n)
    for i in range(n):
        for j in range(i + 1, n):
            if raw_jaccard(rows[i], rows[j]) >= threshold:
                uf.union(i, j)
    return len({uf.find(i) for i in range(n)})


def naive_unique(texts: Iterable[str]) -> int:
    """String-equality count. Evidence only; never gates the stopping rule."""
    return len({str(t).strip() for t in texts})


def stopping_unique_count(texts: Iterable[str]) -> int:
    """The only count that may satisfy a ``unique_ideas >= floor`` target."""
    return unique_count_union_find(texts)


def gate_unique_ge(count: int, floor: int = UNIQUE_IDEAS_FLOOR) -> bool:
    return int(count) >= int(floor)


def gate_unique_ideas_ge(texts: Iterable[str], floor: int = UNIQUE_IDEAS_FLOOR) -> bool:
    """Stopping-rule gate: post-dedup count reaches the floor."""
    return gate_unique_ge(stopping_unique_count(texts), floor)


def collapse_ratio(raw_count: int, post_dedup_count: int) -> float:
    """Fraction of string-unique rows that dedup collapsed away."""
    if raw_count <= 0:
        return 0.0
    return max(0.0, 1.0 - (post_dedup_count / raw_count))


_SYNONYM = {
    "reattempt": "retry",
    "unsuccessful": "failed",
    "beginning": "starting",
    "ms": "milliseconds",
    "keep": "cache",
    "put": "cache",
    "into": "in",
    "under": "behind",
    # memoisation family (TST-0265 planted rewrite vocabulary)
    "memoize": "cache",
    "memoise": "cache",
    "remember": "cache",
    "costly": "expensive",
    "callable": "function",
    "outputs": "results",
    "output": "results",
    "result": "results",
    "indexed": "keyed",
    "ram": "memory",
    "dictionary": "store",
    "dict": "store",
    "expiry": "ttl",
    "expiration": "ttl",
    "timeout": "ttl",
    "removal": "eviction",
    "evict": "eviction",
}


def _norm_syn(text: str) -> set[str]:
    """Synonym-folded content tokens (stop-words dropped before and after folding)."""
    toks = {_SYNONYM.get(t, t) for t in raw_tokens(text)}
    return {t for t in toks if t and t not in _STOPWORDS}


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
    info = components_union_find(texts, threshold)
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
    clustered = components_union_find(texts)
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
