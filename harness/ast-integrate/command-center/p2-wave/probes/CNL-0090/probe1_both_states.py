#!/usr/bin/env python3
"""Probe 1: detector-control then both-states.

Order is load-bearing. A known-present instance must FIRE before any
absence (SILENT on clean) is reported. If the planted-bad fixture does
not fire, this is a fixture-control miss, not a detector success.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = HERE / "probe1-both-states.raw.json"
PLANTED = [
    ("planted_loop.json", "detector-control-known-present"),
    ("planted_paraphrase.json", "planted-paraphrase"),
]
CLEAN = [
    ("clean_productive.json", "known-good-productive"),
    ("clean_refinement.json", "known-good-refinement"),
]


def run_one(name: str, role: str) -> dict:
    path = D.fixture_path(name)
    doc = json.loads(path.read_text(encoding="utf-8"))
    result = D.detect(doc)
    result["role"] = role
    result["fixture_file"] = f"command-center/p2-wave/probes/CNL-0090/fixtures/{name}"
    curve = [
        {
            "round": g["round"],
            "information_units": g["information_units"],
            "subfloor": g["subfloor"],
            "new_claim_ids": g["new_claim_ids"],
            "new_evidence_ids": g["new_evidence_ids"],
            "consecutive_subfloor": g["consecutive_subfloor"],
        }
        for g in result["gain_curve"]
    ]
    print(
        f"{role} fixture={name} fired={result['fired']} silent={result['silent']} "
        f"fired_at={result['fired_at_round']} curve={curve}"
    )
    return result


def main() -> int:
    planted_runs = []
    for name, role in PLANTED:
        result = run_one(name, role)
        planted_runs.append(result)
        if not result["fired"]:
            print(
                f"FAILED:CNL-0090-probe1 fixture-control-miss {name} "
                "did not FIRE; fix the fixture before judging the detector"
            )
            return 1

    clean_runs = []
    false_positives = 0
    for name, role in CLEAN:
        result = run_one(name, role)
        clean_runs.append(result)
        if result["fired"]:
            false_positives += 1

    fpr = false_positives / len(CLEAN)
    if fpr != 0:
        print(f"FAILED:CNL-0090-probe1 false_positive_rate={fpr} (must be 0)")
        return 1

    payload = {
        "probe": "probe1-both-states",
        "unit_id": "CNL-0090",
        "detector_control_first": True,
        "fired_on_bad": True,
        "silent_on_good": True,
        "false_positive_rate": fpr,
        "false_positive_numerator": false_positives,
        "false_positive_denominator": len(CLEAN),
        "floor": D.FLOOR,
        "window": D.WINDOW,
        "planted": [
            {
                "fixture": r["fixture_file"],
                "id": r["fixture_id"],
                "fired": r["fired"],
                "fired_at_round": r["fired_at_round"],
                "gain_curve": [
                    {
                        "round": g["round"],
                        "information_units": g["information_units"],
                        "subfloor": g["subfloor"],
                    }
                    for g in r["gain_curve"]
                ],
            }
            for r in planted_runs
        ],
        "known_good": [
            {
                "fixture": r["fixture_file"],
                "id": r["fixture_id"],
                "silent": r["silent"],
                "gain_curve": [
                    {
                        "round": g["round"],
                        "information_units": g["information_units"],
                        "subfloor": g["subfloor"],
                    }
                    for g in r["gain_curve"]
                ],
            }
            for r in clean_runs
        ],
        "pass": True,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"fired_on_bad=True silent_on_good=True detector_control_first=True "
        f"false_positive_rate={fpr}"
    )
    print("SUCCESS:CNL-0090-probe1 both-states and detector-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
