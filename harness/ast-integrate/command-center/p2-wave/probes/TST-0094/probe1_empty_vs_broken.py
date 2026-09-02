#!/usr/bin/env python3
"""Probe 1: empty harvest and broken harvest are distinguishable.

Catalog test: test_empty_harvest_and_broken_harvest_are_distinguishable.

Three live runs — genuinely-nothing-to-harvest, filter-mismatch,
connection-failure — must produce THREE typed outcomes. A mutant that
collapses every zero-transfer into EMPTY must NOT distinguish them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harvest as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0094.json"
OUT = HERE / "probe1-empty-vs-broken.raw.json"
SENTINEL = "SUCCESS:TST-0094"


def main() -> int:
    demo = H.three_typed_runs()
    pos = H.nonempty_harvest_control()
    expected = demo["expected"]
    by_scenario = {r["scenario"]: r["outcome"] for r in demo["runs"]}

    errors: list[str] = []
    for scenario, want in expected.items():
        got = by_scenario.get(scenario)
        if got != want:
            errors.append(f"{scenario}: want {want} got {got}")

    if not demo["production_distinct"]:
        errors.append(
            f"production outcomes not distinct: {demo['production_outcomes']}"
        )
    if not demo["mutant_collapsed"]:
        errors.append(f"mutant did not collapse: {demo['mutant_outcomes']}")
    if set(demo["production_outcomes"]) == set(demo["mutant_outcomes"]):
        errors.append("production matched mutant (classifier is vacuous)")
    if H.EMPTY in demo["production_outcomes"]:
        errors.append("production emitted EMPTY")
    if not pos["first_ok"]:
        errors.append(f"nonempty harvest was not ok: {pos['first']}")
    if not pos["second_is_nothing_new"]:
        errors.append(
            f"second harvest was not NOTHING_TO_HARVEST: {pos['second']}"
        )
    if pos["first"]["outcome"] == pos["second"]["outcome"]:
        errors.append(
            "first and second harvest of the same session share an outcome"
        )

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("unit_id") != "TST-0094":
            errors.append(f"receipt unit_id {doc.get('unit_id')!r}")
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            errors.append(f"receipt self-declared {doc.get('state')}")
        if SENTINEL not in text:
            errors.append("receipt sentinel absent")
        recorded = (doc.get("evidence") or {}).get("runs") or []
        rec_by = {
            r.get("scenario"): r.get("outcome")
            for r in recorded
            if isinstance(r, dict)
        }
        for scenario, want in expected.items():
            if rec_by.get(scenario) != want:
                errors.append(
                    f"receipt run {scenario}: {rec_by.get(scenario)!r} != {want}"
                )

    report = {
        "probe": "probe1-empty-vs-broken",
        "unit_id": "TST-0094",
        "production_outcomes": demo["production_outcomes"],
        "mutant_outcomes": demo["mutant_outcomes"],
        "production_distinct": demo["production_distinct"],
        "mutant_collapsed": demo["mutant_collapsed"],
        "nonempty_first_ok": pos["first_ok"],
        "second_harvest_nothing_new": pos["second_is_nothing_new"],
        "errors": errors,
        "pass": not errors,
    }
    OUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    if errors:
        print("FAILED:TST-0094-probe1 empty vs broken not distinguished")
        for e in errors:
            print(" ", e)
        return 1
    print(
        "SUCCESS:TST-0094-probe1 three typed outcomes "
        f"{demo['production_outcomes']}; mutant collapsed to EMPTY; "
        "nonempty harvest is HARVESTED then NOTHING_TO_HARVEST"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
