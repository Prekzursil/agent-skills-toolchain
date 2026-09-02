"""Mutation campaign: delete or empty-string each carry field at each hop.

Evidence A: one mutation per hop, catching gate named per hop. A surviving
mutant is a P1 hole and fails the campaign.
"""
from __future__ import annotations

import copy
from typing import Any

from carry import ANCHOR_KEY, HOPS, LICENCE_KEY
from gates import inspect
from pipeline import run_to

MUTATIONS = (
    {"id": "delete_anchor", "key": ANCHOR_KEY, "mode": "delete"},
    {"id": "empty_anchor", "key": ANCHOR_KEY, "mode": "empty"},
    {"id": "delete_licence", "key": LICENCE_KEY, "mode": "delete"},
    {"id": "empty_licence", "key": LICENCE_KEY, "mode": "empty"},
)


def apply_mutation(artifact: dict[str, Any], mode: str, key: str) -> dict[str, Any]:
    mutant = copy.deepcopy(artifact)
    if mode == "delete":
        mutant.pop(key, None)
    elif mode == "empty":
        mutant[key] = ""
    else:
        raise ValueError(f"unknown mutation mode {mode!r}")
    return mutant


def run_campaign() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for hop in HOPS:
        clean = run_to(hop)
        for spec in MUTATIONS:
            mutant = apply_mutation(clean, spec["mode"], spec["key"])
            verdict = inspect(hop, mutant)
            survived = not verdict["fired"]
            expected_field = spec["key"]
            named = verdict["gate_id"]
            rows.append(
                {
                    "mutant_id": f"{hop}/{spec['id']}",
                    "hop": hop,
                    "mutation": spec["id"],
                    "field": spec["key"],
                    "mode": spec["mode"],
                    "catching_gate": named if verdict["fired"] else None,
                    "gate": verdict,
                    "survived": survived,
                    "caught_expected_field": expected_field in (verdict.get("lost_fields") or []),
                }
            )
    survivors = [r for r in rows if r["survived"]]
    empty_vs_missing = _empty_equivalent_to_missing(rows)
    fields_covered = {r["field"] for r in rows}
    hops_covered = {r["hop"] for r in rows}
    return {
        "mutant_count": len(rows),
        "expected_count": len(HOPS) * len(MUTATIONS),
        "surviving_mutants": [s["mutant_id"] for s in survivors],
        "p1_hole": bool(survivors),
        "empty_string_equivalent_to_missing": empty_vs_missing,
        "licence_and_anchor_both_covered": fields_covered == {ANCHOR_KEY, LICENCE_KEY},
        "hops_covered": sorted(hops_covered, key=lambda h: HOPS.index(h)),
        "rows": rows,
    }


def _empty_equivalent_to_missing(rows: list[dict[str, Any]]) -> bool:
    """Empty-string and delete must fire the same named gate on the same field."""
    by = {(r["hop"], r["field"], r["mode"]): r for r in rows}
    for hop in HOPS:
        for key in (ANCHOR_KEY, LICENCE_KEY):
            deleted = by[(hop, key, "delete")]
            emptied = by[(hop, key, "empty")]
            if deleted["survived"] or emptied["survived"]:
                return False
            if deleted["catching_gate"] != emptied["catching_gate"]:
                return False
            if not deleted["catching_gate"]:
                return False
            if key not in deleted["gate"]["lost_fields"]:
                return False
            if key not in emptied["gate"]["lost_fields"]:
                return False
    return True
