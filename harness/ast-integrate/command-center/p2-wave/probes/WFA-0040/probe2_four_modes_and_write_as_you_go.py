#!/usr/bin/env python3
"""Probe 2: four modes are separate columns; write-as-you-go is flagged.

Mechanically independent of probe 1: re-reads the artifact and re-derives
fault-injection observables from mode status without calling extract_one on
the live rows (planted controls are re-extracted as the known-state pair).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import FOUR_MODES, planted_candidates  # noqa: E402
from extractor import extract_one, fault_injection  # noqa: E402

OUT = REPO / "command-center" / "wfa" / "WFA-0040-extract-failure-behaviour.json"
SENTINEL = "SUCCESS:WFA-0040"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0040-probe2 {msg}")
    return 1


def main() -> int:
    plants = {c["id"]: c for c in planted_candidates()}
    four = extract_one(plants["plant-four-modes"])
    agg = extract_one(plants["plant-aggregate-only"])
    mem = extract_one(plants["plant-memory-until-end"])
    wayg = extract_one(plants["plant-write-as-you-go"])
    t_only = extract_one(plants["plant-timeout-only"])

    four_e = [four["modes"][m]["status"] for m in FOUR_MODES]
    if four_e != ["EVIDENCED"] * 4:
        return fail(f"plant-four-modes statuses={four_e}")
    quotes = [four["modes"][m].get("quote") for m in FOUR_MODES]
    if any(q is None for q in quotes):
        return fail("plant-four-modes missing per-mode quotes")
    if len(set(quotes)) < 4:
        return fail("plant-four-modes quotes are not distinct across modes")

    agg_e = [agg["modes"][m]["status"] for m in FOUR_MODES]
    if agg_e != ["UNDEFINED"] * 4:
        return fail(
            f"aggregate catch-all filled modes {agg_e}; a single aggregate "
            "must not hide which mode is missing"
        )
    if not agg["no_failure_behaviour"]:
        return fail("aggregate-only must be no_failure_behaviour")

    if mem["write_as_you_go"].get("status") != "VIOLATION":
        return fail(
            f"memory-until-end not flagged: {mem['write_as_you_go']}"
        )
    if mem["write_as_you_go"].get("flagged") is not True:
        return fail("memory-until-end flagged!=true")
    if wayg["write_as_you_go"].get("status") != "COMPLIANT":
        return fail(f"write-as-you-go plant not COMPLIANT: {wayg['write_as_you_go']}")

    t_st = [t_only["modes"][m]["status"] for m in FOUR_MODES]
    if t_st != ["UNDEFINED", "UNDEFINED", "EVIDENCED", "UNDEFINED"]:
        return fail(f"timeout-only should evidence only timeout, got {t_st}")

    for mode in FOUR_MODES:
        sk = fault_injection(mode, agg["modes"][mode])
        if sk["observable"] != "UNDEFINED":
            return fail(f"aggregate {mode} sketch observable={sk['observable']}")
        sk4 = fault_injection(mode, four["modes"][mode])
        if sk4["observable"] == "UNDEFINED":
            return fail(f"four-mode {mode} sketch has no observable")

    if not OUT.is_file():
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(doc):
        return fail("sentinel absent")
    if "failure_behaviour_aggregate" in doc:
        return fail("artifact has a single aggregate column")
    rows = doc.get("rows") or []
    if not rows:
        return fail("artifact rows empty")
    for row in rows:
        modes = row.get("modes")
        if not isinstance(modes, dict):
            return fail(f"{row.get('candidate_id')} modes not an object")
        keys = tuple(modes.keys())
        missing = [m for m in FOUR_MODES if m not in modes]
        if missing:
            return fail(f"{row.get('candidate_id')} missing modes {missing}")
        if any(k not in FOUR_MODES and k != "aggregate" for k in keys):
            # extra keys ok except a hiding aggregate
            pass
        if "aggregate" in modes:
            return fail(f"{row.get('candidate_id')} has aggregate mode key")
        sketches = row.get("fault_injection") or {}
        for mode in FOUR_MODES:
            st = modes[mode].get("status")
            obs = (sketches.get(mode) or {}).get("observable")
            if st == "UNDEFINED" and obs != "UNDEFINED":
                return fail(
                    f"{row.get('candidate_id')}.{mode} UNDEFINED but "
                    f"observable={obs} (assumed graceful)"
                )
            if st == "EVIDENCED" and (not obs or obs == "UNDEFINED"):
                return fail(
                    f"{row.get('candidate_id')}.{mode} EVIDENCED without observable"
                )

    by_id = {r["candidate_id"]: r for r in rows}
    art_mem = by_id.get("plant-memory-until-end") or {}
    if (art_mem.get("write_as_you_go") or {}).get("status") != "VIOLATION":
        return fail("artifact did not flag memory-until-end")
    art_agg = by_id.get("plant-aggregate-only") or {}
    if [art_agg.get("modes", {}).get(m, {}).get("status") for m in FOUR_MODES] != [
        "UNDEFINED"
    ] * 4:
        return fail("artifact aggregate-only filled a mode")

    payload = {
        "pass": True,
        "probe": "probe2-four-modes-and-write-as-you-go",
        "unit_id": "WFA-0040",
        "four_modes_separate": True,
        "aggregate_does_not_fill_four": True,
        "memory_until_end_flagged": True,
        "write_as_you_go_compliant_unflagged": True,
        "timeout_only_does_not_fill_siblings": True,
        "undefined_sketch_is_undefined": True,
        "artifact_rows": len(rows),
        "independent_of_probe1": "re-reads artifact JSON; does not call extract_all",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "four_separate=True aggregate_empty=True memory_flagged=True "
        f"rows={len(rows)}"
    )
    print("SUCCESS:WFA-0040-probe2 four modes separate; write-as-you-go flagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
