#!/usr/bin/env python3
"""Run the planted-duplicate and planted-distinct controls against a unit list."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from claim_check import check_claim
from fingerprint import collisions_among, fingerprint_parts, jaccard, pair_collides
from planted import (
    DISTINCT_A_ID,
    DISTINCT_B_ID,
    EXACT_ID,
    REWORD_ID,
    ghost_claim,
    inject_distinct,
    inject_duplicates,
)
from scan import scan_units


def _pair_hit(collisions: Sequence[Mapping[str, Any]], left: str, right: str) -> Mapping[str, Any] | None:
    want = tuple(sorted((left, right)))
    for row in collisions:
        got = tuple(sorted((str(row["unit_id_a"]), str(row["unit_id_b"]))))
        if got == want:
            return row
    return None


def run_duplicate_control(units: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    injected = inject_duplicates(units)
    result = scan_units(injected)
    collisions = result["collisions"]
    donor_id = "IMP-0412"
    exact = _pair_hit(collisions, donor_id, EXACT_ID)
    reword = _pair_hit(collisions, donor_id, REWORD_ID)
    ghost = ghost_claim(units)
    claim_hits = check_claim(ghost, units)
    claim_ids = {
        (row["unit_id_a"] if row["unit_id_b"] == ghost["id"] else row["unit_id_b"])
        for row in claim_hits
    }
    return {
        "exact_duplicate_caught": exact is not None,
        "reworded_duplicate_caught": reword is not None,
        "exact_row": dict(exact) if exact else None,
        "reword_row": dict(reword) if reword else None,
        "claim_time_caught_donor": donor_id in claim_ids,
        "claim_time_hit_count": len(claim_hits),
        "injected_collision_pair_count": result["collision_pair_count"],
        "pass": bool(exact and reword and donor_id in claim_ids),
    }


def run_distinct_control(units: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    injected = inject_distinct(units)
    by_id = {u["id"]: u for u in injected}
    a = fingerprint_parts(by_id[DISTINCT_A_ID])
    b = fingerprint_parts(by_id[DISTINCT_B_ID])
    score = jaccard(a.tokens, b.tokens)
    collided = pair_collides(a, b)
    live_a = next((u for u in units if u.get("id") == "IMP-0412"), None)
    live_b = next((u for u in units if u.get("id") == "IMP-0456"), None)
    live_collided = False
    live_jaccard = None
    if live_a and live_b:
        pa, pb = fingerprint_parts(live_a), fingerprint_parts(live_b)
        live_jaccard = round(jaccard(pa.tokens, pb.tokens), 6)
        live_collided = pair_collides(pa, pb)
    similar_vocab = score > 0.05
    same_inputs = a.inputs == b.inputs
    return {
        "distinct_pair_did_not_collide": not collided,
        "planted_jaccard": round(score, 6),
        "planted_same_inputs": same_inputs,
        "similar_vocabulary": similar_vocab,
        "live_imp0412_vs_imp0456_collided": live_collided,
        "live_imp0412_vs_imp0456_jaccard": live_jaccard,
        "pass": (
            not collided
            and same_inputs
            and similar_vocab
            and not live_collided
        ),
    }
