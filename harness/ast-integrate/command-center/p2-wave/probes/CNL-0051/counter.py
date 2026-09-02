#!/usr/bin/env python3
"""F01 unique-idea counter: two mechanically different signals.

Signal L — token-set Jaccard over title+body (lexical overlap).
Signal M — equality of a canonical mechanism key (action|object), independent
of wording. Parameter slots are NOT part of the identity key (one-parameter
forks do not mint a new idea).

Stopping rule: unique_ideas may bind only to corroborated_unique =
min(lexical_unique, mechanism_unique). Pairwise AND of L and M is the wrong
gate: it would miss full rewrites that L cannot see.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

# A priori majority-overlap threshold, chosen before measuring this fixture
# set. Not fitted to make a rewrite look lexical.
LEXICAL_THRESHOLD = 0.50

STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "and",
        "to",
        "for",
        "in",
        "on",
        "with",
        "by",
        "or",
        "as",
        "is",
        "are",
        "that",
        "this",
        "from",
        "be",
        "it",
        "its",
        "at",
        "into",
        "over",
        "than",
        "then",
        "not",
        "no",
        "yes",
        "if",
        "when",
        "whose",
        "which",
        "their",
        "they",
        "them",
        "we",
        "our",
        "every",
        "never",
        "only",
        "must",
        "may",
        "can",
        "does",
        "do",
        "did",
        "has",
        "have",
        "had",
        "was",
        "were",
        "been",
        "being",
        "also",
        "both",
        "each",
        "same",
        "new",
        "one",
        "two",
        "three",
    }
)

TOKEN_RE = re.compile(r"[a-z0-9]+")


def idea_text(idea: dict) -> str:
    return f"{idea.get('title') or ''} {idea.get('body') or ''}"


def tokens(text: str) -> frozenset[str]:
    raw = TOKEN_RE.findall((text or "").lower())
    return frozenset(t for t in raw if t not in STOP and len(t) > 1)


def jaccard(a: str, b: str) -> float:
    A, B = tokens(a), tokens(b)
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def char_ngrams(text: str, n: int = 3) -> frozenset[str]:
    s = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if len(s) < n:
        return frozenset()
    return frozenset(s[i : i + n] for i in range(len(s) - n + 1))


def char_ngram_jaccard(a: str, b: str, n: int = 3) -> float:
    A, B = char_ngrams(a, n), char_ngrams(b, n)
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def _norm_slot(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def mechanism_key(idea: dict) -> str | None:
    mech = idea.get("canonical_mechanism")
    if not isinstance(mech, dict):
        return None
    action = _norm_slot(mech.get("action"))
    obj = _norm_slot(mech.get("object"))
    if not action or not obj:
        return None
    return f"{action}|{obj}"


class UnionFind:
    def __init__(self, ids: Iterable[str]) -> None:
        self.parent = {i: i for i in ids}
        self.rank = {i: 0 for i in ids}

    def find(self, x: str) -> str:
        p = self.parent
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def n_components(self) -> int:
        return len({self.find(i) for i in self.parent})

    def components(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = defaultdict(list)
        for i in self.parent:
            out[self.find(i)].append(i)
        return dict(out)


def pairwise_scores(ideas: list[dict]) -> list[dict]:
    rows = []
    for i, left in enumerate(ideas):
        for right in ideas[i + 1 :]:
            t1, t2 = idea_text(left), idea_text(right)
            k1, k2 = mechanism_key(left), mechanism_key(right)
            jac = round(jaccard(t1, t2), 6)
            c3 = round(char_ngram_jaccard(t1, t2), 6)
            lexical_hit = jac >= LEXICAL_THRESHOLD
            mech_hit = k1 is not None and k1 == k2
            rows.append(
                {
                    "left": left["id"],
                    "right": right["id"],
                    "jaccard": jac,
                    "char3_jaccard": c3,
                    "lexical_hit": lexical_hit,
                    "mechanism_left": k1,
                    "mechanism_right": k2,
                    "mechanism_hit": mech_hit,
                    "pair_or_duplicate": lexical_hit or mech_hit,
                    "pair_and_duplicate": lexical_hit and mech_hit,
                    "contested": lexical_hit != mech_hit,
                }
            )
    return rows


def cluster_counts(ideas: list[dict]) -> dict:
    ids = [idea["id"] for idea in ideas]
    uf_l = UnionFind(ids)
    uf_m = UnionFind(ids)
    uf_or = UnionFind(ids)
    keyed = 0
    unkeyed = 0
    by_id = {idea["id"]: idea for idea in ideas}
    for idea in ideas:
        if mechanism_key(idea) is None:
            unkeyed += 1
        else:
            keyed += 1
    for row in pairwise_scores(ideas):
        if row["lexical_hit"]:
            uf_l.union(row["left"], row["right"])
            uf_or.union(row["left"], row["right"])
        if row["mechanism_hit"]:
            uf_m.union(row["left"], row["right"])
            uf_or.union(row["left"], row["right"])
    lexical_unique = uf_l.n_components()
    mechanism_unique = uf_m.n_components()
    # Unkeyed ideas cannot corroborate a unique increment. They remain
    # separate in mechanism clustering (no key match) so mechanism_unique
    # still counts them. Fail-closed: corroborated count drops them.
    corroborated = min(lexical_unique, mechanism_unique)
    if unkeyed:
        corroborated = min(corroborated, keyed)
    return {
        "n_ideas": len(ideas),
        "keyed": keyed,
        "unkeyed": unkeyed,
        "lexical_unique": lexical_unique,
        "mechanism_unique": mechanism_unique,
        "or_cluster_unique": uf_or.n_components(),
        "corroborated_unique": corroborated,
        "lexical_threshold": LEXICAL_THRESHOLD,
        "lexical_components": {k: sorted(v) for k, v in uf_l.components().items()},
        "mechanism_components": {k: sorted(v) for k, v in uf_m.components().items()},
        "ids": ids,
        "keys": {i: mechanism_key(by_id[i]) for i in ids},
    }


def gaming_check(ideas: list[dict], claimed_unique: int) -> dict:
    counts = cluster_counts(ideas)
    corroborated = counts["corroborated_unique"]
    inflated = int(claimed_unique) > int(corroborated)
    return {
        "claimed_unique": int(claimed_unique),
        "corroborated_unique": corroborated,
        "lexical_unique": counts["lexical_unique"],
        "mechanism_unique": counts["mechanism_unique"],
        "fired": inflated,
        "silent": not inflated,
        "verdict": "FIRE" if inflated else "SILENT",
        "reason": (
            f"claimed_unique={claimed_unique} > corroborated_unique={corroborated}"
            if inflated
            else f"claimed_unique={claimed_unique} <= corroborated_unique={corroborated}"
        ),
        "counts": counts,
    }


def mutant_row(parent: dict, mutant: dict) -> dict:
    t1, t2 = idea_text(parent), idea_text(mutant)
    k1, k2 = mechanism_key(parent), mechanism_key(mutant)
    jac = round(jaccard(t1, t2), 6)
    c3 = round(char_ngram_jaccard(t1, t2), 6)
    lexical_hit = jac >= LEXICAL_THRESHOLD
    mech_hit = k1 is not None and k1 == k2
    return {
        "mutant_id": mutant["id"],
        "parent_id": parent["id"],
        "class": mutant.get("class"),
        "jaccard": jac,
        "char3_jaccard": c3,
        "lexical_hit": lexical_hit,
        "mechanism_hit": mech_hit,
        "caught_as_duplicate": lexical_hit or mech_hit,
        "caught_by_and_gate": lexical_hit and mech_hit,
        "parent_key": k1,
        "mutant_key": k2,
        "parent_tokens": sorted(tokens(t1)),
        "mutant_tokens": sorted(tokens(t2)),
        "token_intersection": sorted(tokens(t1) & tokens(t2)),
        "token_union_size": len(tokens(t1) | tokens(t2)),
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
