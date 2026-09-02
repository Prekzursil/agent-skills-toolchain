#!/usr/bin/env python3
"""RES-0084 unique-idea counter.

Two mechanically different signals. An incoming idea is merged into an
existing cluster (does not increment unique_count) if EITHER:

  (S1) folded token-set Jaccard >= threshold, or
  (S2) canonical mechanism keys are equal after stopword drop, number
       folding, light stemming, and synonym fold.

S1 is the lexical near-duplicate detector. It fires on renames, light
paraphrase, and one-parameter numeric forks that keep most content
tokens. S2 catches full synonym rewrites that land on the same folded
key even when raw Jaccard is low.

Independence: S1 is a graded set-overlap; S2 is boolean key equality.
They share a tokenizer, which is stated as a residual (a third signal
such as embedding cosine is out of scope).

Blind spot (stated, not papered over): a deep paraphrase that uses
out-of-vocabulary wording shares neither a high Jaccard nor a key
with the original, so it lands in the same band as a genuinely
distinct idea. Named settling experiment: RES-0084-DEEP-PARAPHRASE-BAND.
"""
from __future__ import annotations

import re
from typing import Iterable

# Candidate threshold. Live measurement may confirm it sits in the
# rename-vs-distinct gap, or replace it with the gap midpoint.
CANDIDATE_THRESHOLD = 0.50
JACCARD_THRESHOLD = CANDIDATE_THRESHOLD

STOP = frozenset(
    """
    a an the of to for with and or by from into onto over under
    that this these those is are was were be been being as at in on
    it its their his her our your than then so if but not no nor
    using use used via per each any all more most less than inside
    when among without so such also both between after before
    """.split()
)

# Surface synonyms for the planted cache-family seed and its trivial
# rewordings. Incomplete on purpose: OOV full rewrites are the residual
# this counter does not claim to catch.
SYNONYM = {
    "cache": "store",
    "caching": "store",
    "cached": "store",
    "memoize": "store",
    "memoized": "store",
    "memoization": "store",
    "buffer": "store",
    "buffered": "store",
    "dictionary": "store",
    "map": "store",
    "table": "store",
    "expensive": "costly",
    "costly": "costly",
    "function": "fn",
    "functions": "fn",
    "callable": "fn",
    "callables": "fn",
    "result": "output",
    "results": "output",
    "value": "output",
    "values": "output",
    "output": "output",
    "outputs": "output",
    "keyed": "indexed",
    "key": "indexed",
    "keys": "indexed",
    "indexed": "indexed",
    "index": "indexed",
    "memory": "ram",
    "ram": "ram",
    "ttl": "expiry",
    "timeout": "expiry",
    "expiry": "expiry",
    "expiration": "expiry",
    "eviction": "expiry",
    "evict": "expiry",
    "removal": "expiry",
    "remove": "expiry",
    "policy": "rule",
    "scheme": "rule",
}

_TOKEN = re.compile(r"[a-z0-9]+")
_STEM_SUFFIXES = ("tion", "sion", "ness", "ment", "ing", "ers", "ies", "ied", "ed", "es", "s")


def _stem(word: str) -> str:
    for suf in _STEM_SUFFIXES:
        if len(word) > len(suf) + 3 and word.endswith(suf):
            return word[: -len(suf)]
    return word


def content_tokens(text: str, fold_synonyms: bool = True) -> tuple[str, ...]:
    lowered = (text or "").lower().replace("-", " ").replace("_", " ")
    out: list[str] = []
    for raw in _TOKEN.findall(lowered):
        if raw.isdigit():
            out.append("<n>")
            continue
        if raw in STOP:
            continue
        folded = SYNONYM.get(raw, raw) if fold_synonyms else raw
        folded = _stem(folded)
        if fold_synonyms:
            folded = SYNONYM.get(folded, folded)
        if folded in STOP or not folded:
            continue
        out.append(folded)
    return tuple(out)


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def mechanism_key(text: str) -> tuple[str, ...]:
    return tuple(sorted(set(content_tokens(text, fold_synonyms=True))))


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        parent = self.parent
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def n_clusters(self) -> int:
        return len({self.find(i) for i in range(len(self.parent))})


def _pair_merge(
    toks_i: tuple[str, ...],
    toks_j: tuple[str, ...],
    key_i: tuple[str, ...],
    key_j: tuple[str, ...],
    threshold: float,
    use_jaccard: bool,
    use_keys: bool,
) -> bool:
    if use_keys and key_i == key_j and key_i:
        return True
    if use_jaccard and jaccard(toks_i, toks_j) >= threshold:
        return True
    return False


def unique_count_union_find(
    ideas: list[str],
    threshold: float = JACCARD_THRESHOLD,
    *,
    use_jaccard: bool = True,
    use_keys: bool = True,
    fold_synonyms: bool = True,
) -> int:
    """S1 OR S2 clustering via union-find (author path)."""
    n = len(ideas)
    if n == 0:
        return 0
    toks = [content_tokens(s, fold_synonyms=fold_synonyms) for s in ideas]
    keys = [tuple(sorted(set(t))) for t in toks]
    uf = UnionFind(n)
    if use_keys:
        first_key: dict[tuple[str, ...], int] = {}
        for i, key in enumerate(keys):
            if not key:
                continue
            prev = first_key.get(key)
            if prev is None:
                first_key[key] = i
            else:
                uf.union(i, prev)
    if use_jaccard:
        for i in range(n):
            for j in range(i + 1, n):
                if uf.find(i) == uf.find(j):
                    continue
                if jaccard(toks[i], toks[j]) >= threshold:
                    uf.union(i, j)
    return uf.n_clusters()


def unique_count_connected_components(
    ideas: list[str],
    threshold: float = JACCARD_THRESHOLD,
    *,
    use_jaccard: bool = True,
    use_keys: bool = True,
    fold_synonyms: bool = True,
) -> int:
    """S1 OR S2 clustering via BFS (reviewer path — different algorithm)."""
    n = len(ideas)
    if n == 0:
        return 0
    toks = [content_tokens(s, fold_synonyms=fold_synonyms) for s in ideas]
    keys = [tuple(sorted(set(t))) for t in toks]
    adj: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if _pair_merge(
                toks[i], toks[j], keys[i], keys[j], threshold, use_jaccard, use_keys
            ):
                adj[i].append(j)
                adj[j].append(i)
    seen = [False] * n
    components = 0
    for i in range(n):
        if seen[i]:
            continue
        components += 1
        stack = [i]
        seen[i] = True
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if not seen[v]:
                    seen[v] = True
                    stack.append(v)
    return components


def unique_count_jaccard_only(
    ideas: list[str], threshold: float = JACCARD_THRESHOLD, *, fold_synonyms: bool = True
) -> int:
    return unique_count_union_find(
        ideas, threshold, use_jaccard=True, use_keys=False, fold_synonyms=fold_synonyms
    )


def unique_count_keys_only(ideas: list[str]) -> int:
    return unique_count_union_find(ideas, use_jaccard=False, use_keys=True)


def naive_unique(ideas: list[str]) -> int:
    return len(set(ideas))


def gate_unique_ge(count: int, floor: int = 100) -> bool:
    """True = SILENT (accepts the 100-unique target). False = FIRES (rejects)."""
    return count >= floor


def choose_threshold(rename_band_min: float, distinct_band_max: float) -> tuple[float, str]:
    """Place the Jaccard threshold in the measured gap when one exists."""
    if distinct_band_max < CANDIDATE_THRESHOLD <= rename_band_min:
        return CANDIDATE_THRESHOLD, "candidate-in-measured-gap"
    if distinct_band_max < rename_band_min:
        mid = round((distinct_band_max + rename_band_min) / 2.0, 4)
        return mid, "midpoint-of-measured-gap"
    return CANDIDATE_THRESHOLD, "bands-overlap-rely-on-S2"
