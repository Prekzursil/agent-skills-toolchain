"""Mechanical distinctness over (protocols, roles, voting_method, stopping_expression).

Threshold: distance == 0 (identical 4-tuple) is below threshold and must be
named and merged or justified. Names and ids are NOT in the signature.

Blind spot: any dial outside those four axes (novelty/feasibility weights,
anonymity lift timing, oracle identity, wake triggers, evidence-tier bars,
editable_dials that do not change the 4-tuple) is invisible to this metric.
"""
from __future__ import annotations

from typing import Any

THRESHOLD = 0.0


def _sig(preset: dict) -> tuple:
    return (
        tuple(sorted(preset["bound_protocols"])),
        tuple(sorted(preset["roles"])),
        str(preset["voting_method"]),
        str(preset["stopping_expression"]),
    )


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def distance(a: dict, b: dict) -> float:
    jp = 1.0 - jaccard(set(a["bound_protocols"]), set(b["bound_protocols"]))
    jr = 1.0 - jaccard(set(a["roles"]), set(b["roles"]))
    v = 0.0 if a["voting_method"] == b["voting_method"] else 1.0
    s = 0.0 if a["stopping_expression"] == b["stopping_expression"] else 1.0
    return (jp + jr + v + s) / 4.0


def cluster_by_signature(presets: list[dict]) -> dict[tuple, list[str]]:
    buckets: dict[tuple, list[str]] = {}
    for p in presets:
        buckets.setdefault(_sig(p), []).append(p["id"])
    for ids in buckets.values():
        ids.sort()
    return buckets


def below_threshold_pairs(presets: list[dict]) -> list[dict]:
    by_id = {p["id"]: p for p in presets}
    pairs = []
    buckets = cluster_by_signature(presets)
    for sig, ids in buckets.items():
        if len(ids) < 2:
            continue
        for i, left in enumerate(ids):
            for right in ids[i + 1 :]:
                d = distance(by_id[left], by_id[right])
                survivor = min(ids)
                pairs.append(
                    {
                        "left": left,
                        "right": right,
                        "distance": d,
                        "below_threshold": d <= THRESHOLD,
                        "disposition": "merged",
                        "surviving_id": survivor,
                        "justification": (
                            "identical bound-protocol set, role set, voting "
                            "method and stopping expression; names/ids differ "
                            "and are not part of the signature"
                        ),
                    }
                )
    pairs.sort(key=lambda r: (r["left"], r["right"]))
    return pairs


def nearest_neighbours(presets: list[dict]) -> list[dict]:
    rows = []
    for i, a in enumerate(presets):
        best: dict[str, Any] | None = None
        for j, b in enumerate(presets):
            if i == j:
                continue
            d = distance(a, b)
            cand = {
                "id": a["id"],
                "neighbour_id": b["id"],
                "distance": d,
                "same_signature": d <= THRESHOLD,
            }
            if best is None:
                best = cand
                continue
            if d < best["distance"] or (
                d == best["distance"] and b["id"] < best["neighbour_id"]
            ):
                best = cand
        rows.append(best)
    rows.sort(key=lambda r: r["id"])
    return rows


def pair_count(n: int) -> int:
    return n * (n - 1) // 2


def analyse(presets: list[dict]) -> dict:
    n = len(presets)
    buckets = cluster_by_signature(presets)
    distinct = len(buckets)
    below = below_threshold_pairs(presets)
    nn = nearest_neighbours(presets)
    surviving = sorted({min(ids) for ids in buckets.values()})
    merged_away = sorted(
        pid
        for ids in buckets.values()
        for pid in ids
        if pid != min(ids)
    )
    return {
        "preset_count": n,
        "pair_count": pair_count(n),
        "distinct_signature_count": distinct,
        "floor": 64,
        "floor_met": distinct >= 64,
        "threshold": THRESHOLD,
        "threshold_meaning": (
            "distance==0 on the 4-tuple (bound protocols, roles, voting_method, "
            "stopping_expression); names are excluded"
        ),
        "below_threshold_pair_count": len(below),
        "below_threshold_pairs": below,
        "merged_away_ids": merged_away,
        "surviving_ids": surviving,
        "nearest_neighbours": nn,
        "blind_spot": (
            "Novelty/feasibility weights, anonymity-lift timing, oracle "
            "identity, wake triggers, evidence-tier bars, and any editable "
            "dial that does not change the 4-tuple are invisible. A pair can "
            "pass this metric and still be a mechanism-duplicate on an "
            "unscored dial. The corpus itself is a catalog-cited reconstruction "
            "because 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this "
            "worktree; substituting the original library can change the counts."
        ),
    }


def plant_renamed_duplicate(presets: list[dict], source_id: str, new_id: str) -> list[dict]:
    src = next(p for p in presets if p["id"] == source_id)
    clone = dict(src)
    clone["id"] = new_id
    clone["name"] = src["name"] + "-renamed-id"
    clone["clone_of"] = source_id
    return list(presets) + [clone]


def prefix_distinct(presets: list[dict], order: list[str], n: int) -> dict:
    by_id = {p["id"]: p for p in presets}
    sub = [by_id[i] for i in order[:n]]
    buckets = cluster_by_signature(sub)
    names = {p["name"] for p in sub}
    return {
        "n": n,
        "unique_names": len(names),
        "unique_signatures": len(buckets),
        "pair_count": pair_count(n),
    }
