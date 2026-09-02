#!/usr/bin/env python3
"""Instantiate a materialized preset against a fixture task."""
from __future__ import annotations

from common import resolve_against_base


def instantiate(preset: dict, base: dict, task: dict) -> dict:
    spec = resolve_against_base(preset, base)
    roles = spec["roles"]
    roster = []
    for role in roles:
        if role.get("conditional"):
            roster.append({
                "seat": role["id"],
                "template": role["template"],
                "votes": bool(role.get("votes")),
                "status": "unseated-until-split-or-capture",
                "recruited": True,
            })
            continue
        entry = {
            "seat": role["id"],
            "template": role["template"],
            "votes": bool(role.get("votes")),
            "status": "seated",
        }
        if role.get("recruited"):
            entry["recruitment"] = "per-manuscript"
            entry["coi_screen"] = spec["recruitment"].get("coi_screen", False)
        roster.append(entry)

    schedule = []
    bindings = list(spec.get("protocol_bindings") or [])
    rec = spec.get("recruitment") or {}
    anon = spec.get("anonymity") or {}
    reb = spec.get("rebuttal") or {}
    integ = spec.get("integrity") or {}

    if rec.get("mode") == "per-manuscript":
        schedule.append("recruit-and-coi-screen")
    if "P45" in bindings:
        schedule.append("P45")
    if integ.get("seal_first_round") or "P23" in bindings:
        schedule.append("P23")
    if "P20" in bindings:
        schedule.append("P20")
    if reb.get("max_rounds", 0) > 0:
        schedule.append(f"author-rebuttal-x{reb['max_rounds']}-depth{reb.get('depth', 0)}")
    if "P25" in bindings:
        schedule.append("P25")
    if integ.get("two_reviewer_capture") or "P24" in bindings:
        schedule.append("P24")
    if anon.get("level") == "blind-then-revealed":
        schedule.append(f"anonymity-lift:{anon.get('lift_phase')}")
    if "P46" in bindings and "P45" not in bindings:
        schedule.append("P46")
        schedule.append("rubric-verdict")

    # de-dup while preserving order
    seen = set()
    protocol_schedule = []
    for step in schedule:
        if step not in seen:
            seen.add(step)
            protocol_schedule.append(step)

    profile = {
        "roster": roster,
        "protocol_schedule": protocol_schedule,
        "voting_method": spec["voting"]["method"],
        "stopping_expression": spec["stopping"]["expression"],
        "anonymity_level": anon.get("level"),
        "lift_phase": anon.get("lift_phase"),
        "recruitment_mode": rec.get("mode"),
        "rebuttal_max_rounds": reb.get("max_rounds", 0),
        "capture_gate": bool(integ.get("two_reviewer_capture")),
        "task_id": task["id"],
        "preset_id": preset["id"],
        "migration": spec["migration"],
    }
    return profile


def fingerprint(profile: dict) -> dict:
    roles = tuple(sorted(
        f"{r['seat']}:{r['template']}:votes={r['votes']}"
        for r in profile["roster"]
        if r.get("status") != "unseated-until-split-or-capture"
    ))
    return {
        "roles": roles,
        "protocol_schedule": tuple(profile["protocol_schedule"]),
        "voting_method": profile["voting_method"],
        "stopping_expression": profile["stopping_expression"],
        "anonymity_level": profile.get("anonymity_level"),
        "recruitment_mode": profile.get("recruitment_mode"),
        "rebuttal_max_rounds": profile.get("rebuttal_max_rounds"),
        "capture_gate": profile.get("capture_gate"),
    }


def differential(this_fp: dict, sibling_fp: dict) -> dict:
    axes = sorted(set(this_fp) | set(sibling_fp))
    differing = [a for a in axes if this_fp.get(a) != sibling_fp.get(a)]
    return {
        "distance": len(differing),
        "differing_axes": differing,
        "identical_axes": [a for a in axes if a not in differing],
        "measurable": len(differing) >= 3,
    }
