#!/usr/bin/env python3
"""F01 unique-idea counter (CNL-0051 operationalization, local to CNL-0052).

Two mechanically different signals. An incoming idea is merged into an existing
cluster (does not increment unique_count) if EITHER:

  (S1) token-set Jaccard >= JACCARD_THRESHOLD, or
  (S2) canonical mechanism keys are equal after stopword drop, number
       stripping, light stemming, and synonym fold.

S1 catches exact rename / high-overlap paraphrase / one-parameter forks.
S2 catches full rewrites that stay inside the synonym table.

Genuinely distinct mechanisms must differ on BOTH signals or they will be
over-merged. The Jaccard threshold sits below the rename band (0.93-1.00)
measured in the CNL-0051 brief and above typical distinct-pair overlap.
"""
from __future__ import annotations

import re
from typing import Iterable

JACCARD_THRESHOLD = 0.50

STOP = frozenset(
    """
    a an the of to for with and or by from into onto over under
    that this these those is are was were be been being as at in on
    it its their his her our your than then so if but not no nor
    using use used via per each any all more most less than
    inside within without among between against during
    about after before around across behind beside besides
    through toward towards until unless while because
    """.split()
)

# Fold surface synonyms onto a small mechanism vocabulary. Incomplete on
# purpose: out-of-vocabulary full rewrites are the residual F01 does not
# claim to catch (CNL-0051 already names that blind spot).
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


def _alnum_words(text: str) -> list[str]:
    lowered = (text or "").lower().replace("-", " ").replace("_", " ")
    return _TOKEN.findall(lowered)


def raw_tokens(text: str) -> tuple[str, ...]:
    """Lexical tokens for S1: stopwords and digits dropped, no synonym fold.

    This is the Jaccard signal that fires on renames (high overlap) and is
    blind to a full rewrite that keeps almost no surface words.
    """
    out: list[str] = []
    for raw in _alnum_words(text):
        if raw.isdigit():
            out.append("<n>")
            continue
        if raw in STOP:
            continue
        out.append(raw)
    return tuple(out)


def folded_tokens(text: str) -> tuple[str, ...]:
    """Canonical tokens for S2: synonym fold + light stem."""
    out: list[str] = []
    for raw in _alnum_words(text):
        if raw.isdigit():
            out.append("<n>")
            continue
        if raw in STOP:
            continue
        folded = SYNONYM.get(raw, raw)
        folded = _stem(folded)
        folded = SYNONYM.get(folded, folded)
        if folded in STOP or not folded:
            continue
        out.append(folded)
    return tuple(out)


def content_tokens(text: str) -> tuple[str, ...]:
    """Back-compat alias: raw lexical tokens (S1)."""
    return raw_tokens(text)


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def mechanism_key(text: str) -> tuple[str, ...]:
    return tuple(sorted(set(folded_tokens(text))))


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


def unique_count_union_find(
    ideas: list[str], threshold: float = JACCARD_THRESHOLD
) -> int:
    """S1 OR S2 clustering via union-find (author path)."""
    n = len(ideas)
    if n == 0:
        return 0
    toks = [raw_tokens(s) for s in ideas]
    keys = [mechanism_key(s) for s in ideas]
    uf = UnionFind(n)
    first_key: dict[tuple[str, ...], int] = {}
    for i, key in enumerate(keys):
        prev = first_key.get(key)
        if prev is None:
            first_key[key] = i
        else:
            uf.union(i, prev)
    for i in range(n):
        for j in range(i + 1, n):
            if uf.find(i) == uf.find(j):
                continue
            if jaccard(toks[i], toks[j]) >= threshold:
                uf.union(i, j)
    return uf.n_clusters()


def unique_count_connected_components(
    ideas: list[str], threshold: float = JACCARD_THRESHOLD
) -> int:
    """S1 OR S2 clustering via BFS connected components (reviewer path)."""
    n = len(ideas)
    if n == 0:
        return 0
    toks = [raw_tokens(s) for s in ideas]
    keys = [mechanism_key(s) for s in ideas]
    adj: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if keys[i] == keys[j] or jaccard(toks[i], toks[j]) >= threshold:
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
    ideas: list[str], threshold: float = JACCARD_THRESHOLD
) -> int:
    n = len(ideas)
    if n == 0:
        return 0
    toks = [raw_tokens(s) for s in ideas]
    uf = UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if jaccard(toks[i], toks[j]) >= threshold:
                uf.union(i, j)
    return uf.n_clusters()


def naive_unique(ideas: list[str]) -> int:
    return len(set(ideas))


def gate_unique_ge(count: int, floor: int = 100) -> bool:
    return count >= floor
