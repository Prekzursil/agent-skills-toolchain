#!/usr/bin/env python3
"""Probe 1: stub each hybrid subsystem; live journey goes red every time.

Mechanically re-runs the stub campaign and diffs against TEST-PLAN.json.
A stub that leaves the harvest COMPLETE means that hop is not exercised.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import engine as E  # noqa: E402

ART = REPO / "command-center/phase3/A9/TEST-PLAN.json"


def plan_body(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    merged = dict(doc)
    merged.update(report)
    return merged


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0064-probe1 TEST-PLAN.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = plan_body(doc)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:ARC-0064-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0064" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0064-probe1 sentinel absent")
        return 1
    live = E.run_stub_campaign()
    print(f"clean_green={live['clean_green']} verdict={live['clean'].get('verdict')}")
    print(f"library={live['clean'].get('library')}")
    print(f"all_stubs_went_red={live['all_stubs_went_red']}")
    if not live["clean_green"]:
        print("FAILED:ARC-0064-probe1 clean journey not green")
        return 1
    if live["clean"].get("library") != E.LIBRARY:
        print("FAILED:ARC-0064-probe1 clean harvest not shared reducer")
        return 1
    if not live["all_stubs_went_red"]:
        print("FAILED:ARC-0064-probe1 a stub stayed green")
        return 1
    art_rows = {
        r.get("stubbed_subsystem"): r
        for r in (body.get("stub_mutations") or [])
        if isinstance(r, dict)
    }
    if set(art_rows) != set(E.SUBSYSTEMS):
        print(f"FAILED:ARC-0064-probe1 stub set drift {sorted(art_rows)} vs {list(E.SUBSYSTEMS)}")
        return 1
    for row in live["stubs"]:
        name = row["stubbed_subsystem"]
        art = art_rows[name]
        print(
            f"stub {name} went_red={row['went_red']} "
            f"verdict={row['stubbed_verdict']} hops={row['hops_assert_ok']}"
        )
        if row["went_red"] is not True:
            print(f"FAILED:ARC-0064-probe1 {name} did not go red")
            return 1
        if art.get("went_red") is not True:
            print(f"FAILED:ARC-0064-probe1 artifact {name} went_red not true")
            return 1
        if str(art.get("stubbed_verdict")) != str(row["stubbed_verdict"]):
            print(
                f"FAILED:ARC-0064-probe1 {name} verdict drift "
                f"{art.get('stubbed_verdict')} vs {row['stubbed_verdict']}"
            )
            return 1
    journeys = body.get("journeys") or []
    if not journeys or len((journeys[0].get("hops") or [])) < 5:
        print("FAILED:ARC-0064-probe1 journey hops missing")
        return 1
    for hop in journeys[0]["hops"]:
        if hop.get("silent_short_circuit") is True:
            print(f"FAILED:ARC-0064-probe1 hop {hop.get('subsystem')} silently short-circuited")
            return 1
        if hop.get("assert_ok") is not True:
            print(f"FAILED:ARC-0064-probe1 clean hop {hop.get('subsystem')} not ok in artifact")
            return 1
        if not str(hop.get("artifact") or "").strip():
            print(f"FAILED:ARC-0064-probe1 hop {hop.get('subsystem')} missing artifact")
            return 1
    if body.get("inputs_on_disk", {}).get("a9_design_present") is True:
        print("FAILED:ARC-0064-probe1 artifact claimed live A9 DESIGN")
        return 1
    print("SUCCESS:ARC-0064-probe1 stub-mutation per subsystem both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
