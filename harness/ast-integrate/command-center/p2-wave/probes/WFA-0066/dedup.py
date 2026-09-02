"""Mechanism-level dedup: incidence overlap AND blind discrimination.

Collapse requires both signals. Incidence Jaccard alone can mark a shared
source, not a shared mechanism. Ids are aliased via duplicate-of edges;
they are never deleted. Leverage ranking uses independent upstream sources,
not artifact frequency.
"""
from __future__ import annotations

import re
from typing import Any

from corpus import incidence_sets, mechanism_index, upstream_map

STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "of",
        "to",
        "for",
        "in",
        "on",
        "is",
        "are",
        "be",
        "as",
        "that",
        "this",
        "it",
        "its",
        "by",
        "with",
        "from",
        "not",
        "no",
        "so",
        "than",
        "then",
        "into",
        "over",
        "must",
        "should",
        "would",
        "can",
        "only",
        "also",
        "their",
        "they",
        "them",
        "when",
        "already",
        "means",
        "rather",
        "than",
    }
)
TOKEN = re.compile(r"[a-z0-9]+")
INCIDENCE_THRESHOLD = 0.70
ACCURACY_FLOOR = 0.70


def tokens(text: str) -> frozenset[str]:
    words = TOKEN.findall((text or "").casefold())
    return frozenset(w for w in words if len(w) >= 3 and w not in STOP)


def jaccard(a: frozenset[str] | set[str], b: frozenset[str] | set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def incidence_jaccard(left: set[str], right: set[str]) -> float:
    return jaccard(left, right)


def discriminate(left: dict, right: dict) -> dict:
    """Assign held-out examples using only the two definitions as prototypes."""
    def_a = tokens(str(left.get("definition") or ""))
    def_b = tokens(str(right.get("definition") or ""))
    labeled: list[tuple[str, str]] = []
    for ex in left.get("examples") or []:
        labeled.append((str(left["id"]), str(ex)))
    for ex in right.get("examples") or []:
        labeled.append((str(right["id"]), str(ex)))
    correct = 0
    ties = 0
    margins: list[float] = []
    for home, text in labeled:
        tok = tokens(text)
        sa = jaccard(tok, def_a)
        sb = jaccard(tok, def_b)
        margins.append(abs(sa - sb))
        if sa == sb:
            ties += 1
            continue
        pred = str(left["id"]) if sa > sb else str(right["id"])
        if pred == home:
            correct += 1
    n = len(labeled)
    accuracy = correct / n if n else 0.0
    mean_margin = sum(margins) / len(margins) if margins else 0.0
    return {
        "left": str(left["id"]),
        "right": str(right["id"]),
        "n": n,
        "correct": correct,
        "ties": ties,
        "accuracy": round(accuracy, 4),
        "mean_margin": round(mean_margin, 4),
        "definition_jaccard": round(jaccard(def_a, def_b), 4),
        "indistinguishable": bool(n > 0 and accuracy < ACCURACY_FLOOR),
        "method": "definition-prototype-jaccard",
    }


def example_knn_accuracy(left: dict, right: dict) -> dict:
    """Leave-one-out 1-NN over example texts only (no definition tokens)."""
    labeled: list[tuple[str, frozenset[str]]] = []
    for ex in left.get("examples") or []:
        labeled.append((str(left["id"]), tokens(str(ex))))
    for ex in right.get("examples") or []:
        labeled.append((str(right["id"]), tokens(str(ex))))
    if len(labeled) < 2:
        return {
            "left": str(left["id"]),
            "right": str(right["id"]),
            "n": len(labeled),
            "accuracy": 0.0,
            "indistinguishable": True,
            "method": "example-leave-one-out-1nn",
        }
    correct = 0
    for i, (home, tok) in enumerate(labeled):
        best_s = -1.0
        best_id = ""
        for j, (oid, otok) in enumerate(labeled):
            if i == j:
                continue
            score = jaccard(tok, otok)
            if score > best_s:
                best_s = score
                best_id = oid
        if best_id == home:
            correct += 1
    n = len(labeled)
    accuracy = correct / n
    return {
        "left": str(left["id"]),
        "right": str(right["id"]),
        "n": n,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "indistinguishable": bool(accuracy < ACCURACY_FLOOR),
        "method": "example-leave-one-out-1nn",
    }


class _DSU:
    def __init__(self, ids: list[str], scores: dict[str, float]):
        self.parent = {i: i for i in ids}
        self.scores = scores

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        sa, sb = self.scores.get(ra, 0.0), self.scores.get(rb, 0.0)
        if sa > sb or (sa == sb and ra < rb):
            self.parent[rb] = ra
        else:
            self.parent[ra] = rb


def independent_sources(art_ids: set[str], upstream: dict[str, str]) -> set[str]:
    return {upstream[a] for a in art_ids if a in upstream}


def leverage_score(indep: int, severity: int, impact: int) -> int:
    return int(indep) * int(severity) * int(impact)


def pair_ids(ids: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    ordered = sorted(ids)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            out.append((a, b))
    return out


def evaluate(corpus: dict, incidence_only: bool = False) -> dict[str, Any]:
    mechs = mechanism_index(corpus)
    ids = sorted(mechs)
    inc = incidence_sets(corpus)
    upstream = upstream_map(corpus)
    threshold = float(corpus.get("incidence_suspect_threshold") or INCIDENCE_THRESHOLD)

    pre_rows = []
    for mid in ids:
        arts = inc[mid]
        indep = independent_sources(arts, upstream)
        sev = int(mechs[mid].get("severity") or 1)
        imp = int(mechs[mid].get("decision_impact") or 1)
        pre_rows.append(
            {
                "id": mid,
                "artifact_count": len(arts),
                "independent_source_count": len(indep),
                "independent_sources": sorted(indep),
                "severity": sev,
                "decision_impact": imp,
                "leverage_score": leverage_score(len(indep), sev, imp),
                "single_source": len(indep) == 1,
            }
        )
    pre_rank_lev = _rank(pre_rows, "leverage_score")
    pre_rank_freq = _rank(pre_rows, "artifact_count")
    pre_score = {r["id"]: float(r["leverage_score"]) for r in pre_rows}

    pairs = []
    dsu = _DSU(ids, pre_score)
    for a, b in pair_ids(ids):
        jac = incidence_jaccard(inc[a], inc[b])
        suspect = jac >= threshold
        disc = discriminate(mechs[a], mechs[b])
        collapse = bool(suspect and (incidence_only or disc["indistinguishable"]))
        row = {
            "left": a,
            "right": b,
            "incidence_jaccard": round(jac, 4),
            "suspect": suspect,
            "discrimination": disc,
            "collapse": collapse,
            "reason": _reason(suspect, disc["indistinguishable"], incidence_only, collapse),
        }
        pairs.append(row)
        if collapse:
            dsu.union(a, b)

    alias_edges = []
    canonical_of = {}
    for mid in ids:
        root = dsu.find(mid)
        canonical_of[mid] = root
        if mid != root:
            alias_edges.append(
                {
                    "alias": mid,
                    "canonical": root,
                    "from": mid,
                    "to": root,
                    "relation": "duplicate-of",
                }
            )

    union_inc: dict[str, set[str]] = {mid: set(inc[mid]) for mid in ids}
    for mid in ids:
        root = canonical_of[mid]
        if mid != root:
            union_inc[root] |= inc[mid]

    post_rows = []
    for mid in ids:
        aliased = mid != canonical_of[mid]
        arts = union_inc[mid] if not aliased else inc[mid]
        indep = independent_sources(arts, upstream)
        sev = int(mechs[mid].get("severity") or 1)
        imp = int(mechs[mid].get("decision_impact") or 1)
        post_rows.append(
            {
                "id": mid,
                "status": "ALIASED" if aliased else "CANONICAL",
                "canonical_id": canonical_of[mid],
                "artifact_count": len(arts),
                "independent_source_count": len(indep),
                "independent_sources": sorted(indep),
                "severity": sev,
                "decision_impact": imp,
                "leverage_score": leverage_score(len(indep), sev, imp),
                "single_source": len(indep) == 1,
                "ranked": not aliased,
            }
        )

    ranked_post = [r for r in post_rows if r["ranked"]]
    post_rank_lev = _rank(ranked_post, "leverage_score")
    post_rank_freq = _rank(ranked_post, "artifact_count")

    survivor_deltas = []
    for edge in alias_edges:
        surv = edge["canonical"]
        before = next(r for r in pre_rows if r["id"] == surv)
        after = next(r for r in post_rows if r["id"] == surv)
        survivor_deltas.append(
            {
                "canonical_id": surv,
                "alias_id": edge["alias"],
                "leverage_before": before["leverage_score"],
                "leverage_after": after["leverage_score"],
                "independent_before": before["independent_source_count"],
                "independent_after": after["independent_source_count"],
                "artifact_count_before": before["artifact_count"],
                "artifact_count_after": after["artifact_count"],
                "rank_before": pre_rank_lev[surv],
                "rank_after": post_rank_lev[surv],
            }
        )

    echo = next((r for r in post_rows if r["id"] == "MECH-ECHO-COPY"), None)
    freq_vs_lev = None
    if echo is not None:
        freq_vs_lev = {
            "id": "MECH-ECHO-COPY",
            "frequency_rank_after": post_rank_freq[echo["id"]],
            "leverage_rank_after": post_rank_lev[echo["id"]],
            "artifact_count": echo["artifact_count"],
            "independent_source_count": echo["independent_source_count"],
            "single_source": echo["single_source"],
            "disagreement": post_rank_freq[echo["id"]] != post_rank_lev[echo["id"]],
        }

    retained = sorted(ids)
    return {
        "incidence_only": incidence_only,
        "threshold": threshold,
        "accuracy_floor": ACCURACY_FLOOR,
        "mechanism_ids": retained,
        "ids_deleted": [],
        "pair_verdicts": pairs,
        "collapses": [p for p in pairs if p["collapse"]],
        "duplicate_of_edges": alias_edges,
        "canonical_of": canonical_of,
        "ranking_before": _ordered(pre_rows, pre_rank_lev),
        "ranking_after": _ordered(ranked_post, post_rank_lev),
        "frequency_ranking_after": _ordered(ranked_post, post_rank_freq),
        "all_rows_after": post_rows,
        "ranking_delta": {
            "ranked_count_before": len(pre_rows),
            "ranked_count_after": len(ranked_post),
            "alias_count": len(alias_edges),
            "survivor_deltas": survivor_deltas,
            "frequency_vs_leverage": freq_vs_lev,
        },
    }


def _reason(suspect: bool, indist: bool, incidence_only: bool, collapse: bool) -> str:
    if incidence_only and collapse:
        return "incidence-only-mutant"
    if collapse:
        return "both-signals"
    if suspect and not indist:
        return "shared-source-not-same-mechanism"
    if indist and not suspect:
        return "indistinguishable-but-incidence-below-threshold"
    return "distinct"


def _rank(rows: list[dict], key: str) -> dict[str, int]:
    ordered = sorted(rows, key=lambda r: (-int(r[key]), str(r["id"])))
    return {r["id"]: i + 1 for i, r in enumerate(ordered)}


def _ordered(rows: list[dict], ranks: dict[str, int]) -> list[dict]:
    out = []
    for row in rows:
        item = dict(row)
        item["rank"] = ranks[row["id"]]
        out.append(item)
    return sorted(out, key=lambda r: (r["rank"], r["id"]))


def same_canonical(result: dict, a: str, b: str) -> bool:
    mapping = result["canonical_of"]
    return mapping[a] == mapping[b]


def is_aliased(result: dict, mid: str) -> bool:
    return result["canonical_of"][mid] != mid


example_knn_accuracy = example_knn_accuracy
