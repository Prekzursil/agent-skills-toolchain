#!/usr/bin/env python3
"""Named flatten-point and yield-curve formulas for RES-0165.

Definitions (settled before any number is written):

* unique(texts) = union-find cluster count (S1 Jaccard OR S2 folded key).
* marginal_unique(n) = unique(researchers[0:n]) - unique(researchers[0:n-1]).
* same-prompt noise floor = unique(clone_a + clone_b) - unique(clone_a).
  Any purported added value at or below that floor is not real.
* flatten_n = smallest n >= PERSIST such that the last PERSIST researchers
  each have marginal_unique <= max(noise_floor, YIELD_FLOOR).
* contradiction coverage uses planted (id, polarity) pairs, not Jaccard,
  because GAMEABLE vs RESISTANT share a long prefix and would merge.

Cost is agent-count (one unit per researcher). Token telemetry is absent
on the constructed fan-out and is not invented.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

from cluster import author_unique, reviewer_unique, string_unique

PERSIST = 2
YIELD_FLOOR = 0  # new clustered claims; clone floor is usually 0
UNIT_COST = 1.0


def jaccard_sets(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def concat(researchers: Sequence[Sequence[str]]) -> list[str]:
    out: list[str] = []
    for r in researchers:
        out.extend(r)
    return out


def yield_curve(
    researchers: Sequence[Sequence[str]],
    *,
    contradiction_pairs: Sequence[tuple[str, str]] | None = None,
    finding_ids: Sequence[Sequence[str]] | None = None,
    unique_fn=author_unique,
) -> list[dict[str, Any]]:
    """Walk N=1..len(researchers).

    Distinct claims are finding-id union (S1). Clustered text unique is the
    paraphrase rail (S2) used for the same-prompt noise floor. Naive string
    unique is the known-broken counter.
    """
    pairs = list(contradiction_pairs or [])
    curve: list[dict[str, Any]] = []
    seen_texts: list[str] = []
    seen_ids: set[str] = set()
    prev_ids = 0
    prev_u = 0
    prev_naive = 0
    for i, claims in enumerate(researchers, 1):
        seen_texts.extend(claims)
        if finding_ids is not None:
            seen_ids.update(finding_ids[i - 1])
        u = unique_fn(seen_texts)
        naive = string_unique(seen_texts)
        id_count = len(seen_ids) if finding_ids is not None else u
        id_marginal = id_count - prev_ids
        clustered_marginal = u - prev_u
        naive_marginal = naive - prev_naive
        covered = 0
        if pairs and finding_ids is not None:
            for left, right in pairs:
                if left in seen_ids and right in seen_ids:
                    covered += 1
        coverage = (covered / float(len(pairs))) if pairs else None
        curve.append(
            {
                "n": i,
                "cumulative_unique": id_count,
                "marginal_unique": id_marginal,
                "clustered_cumulative": u,
                "clustered_marginal": clustered_marginal,
                "naive_cumulative": naive,
                "naive_marginal": naive_marginal,
                "cost": round(i * UNIT_COST, 6),
                "marginal_per_cost": id_marginal / UNIT_COST,
                "contradiction_pairs_covered": covered if pairs else None,
                "contradiction_coverage": coverage,
            }
        )
        prev_ids = id_count
        prev_u = u
        prev_naive = naive
    return curve


def flatten_n(
    curve: Sequence[MappingLike],
    *,
    noise_floor: int,
    persist: int = PERSIST,
    yield_floor: int = YIELD_FLOOR,
    min_n: int = 2,
) -> int | None:
    """First n>=min_n at which the last `persist` id-marginals are <= floor.

    n=1 is warmup (the first researcher always adds the seed set). Same-prompt
    clustered added value is the noise floor; id-marginal at or below that
    floor is not real yield.
    """
    floor = max(int(noise_floor), int(yield_floor))
    if len(curve) < persist:
        return None
    start = max(persist - 1, min_n - 1)
    for i in range(start, len(curve)):
        window = curve[i - persist + 1 : i + 1]
        if any(int(row["n"]) < min_n for row in window):
            continue
        if all(int(row["marginal_unique"]) <= floor for row in window):
            return int(curve[i]["n"])
    return None


def noise_floor_from_clone(original: Sequence[str], clone: Sequence[str]) -> dict[str, Any]:
    u_a = author_unique(list(original))
    u_ab = author_unique(list(original) + list(clone))
    naive_a = string_unique(list(original))
    naive_ab = string_unique(list(original) + list(clone))
    clustered_added = u_ab - u_a
    naive_added = naive_ab - naive_a
    return {
        "clustered_unique_a": u_a,
        "clustered_unique_ab": u_ab,
        "clustered_added": clustered_added,
        "naive_unique_a": naive_a,
        "naive_unique_ab": naive_ab,
        "naive_added": naive_added,
        "reviewer_unique_ab": reviewer_unique(list(original) + list(clone)),
        "author_reviewer_agree": author_unique(list(original) + list(clone))
        == reviewer_unique(list(original) + list(clone)),
        "self_overlap_ids": None,
        "rule": (
            "same-prompt clone: clustered added value is the noise floor; "
            "naive string-unique added value is not real yield"
        ),
    }


# typing alias without importing Mapping in flatten signature for py3.9
MappingLike = dict[str, Any]


def pairwise_id_overlap(
    id_sets: Sequence[Iterable[str]],
) -> list[dict[str, Any]]:
    rows = []
    sets = [set(s) for s in id_sets]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            rows.append(
                {
                    "a": i + 1,
                    "b": j + 1,
                    "jaccard": round(jaccard_sets(sets[i], sets[j]), 6),
                    "intersection": len(sets[i] & sets[j]),
                    "union": len(sets[i] | sets[j]),
                }
            )
    return rows
