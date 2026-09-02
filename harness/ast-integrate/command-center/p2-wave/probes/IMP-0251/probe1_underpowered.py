#!/usr/bin/env python3
"""Probe 1: statistical-review both-states.

Underpowered comparison flagged; adequately powered one not flagged.
A result reported without an effect size is flagged; the powered fixture
that includes effect_size is not flagged for that reason.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(LIB))

from science_blueprints.library import load_library, omission_gate  # noqa: E402
from science_blueprints.power import PerRunThresholdTuneError, load_thresholds  # noqa: E402
from science_blueprints.statistical_review import (  # noqa: E402
    missing_effect_size_fixture,
    powered_fixture,
    review,
    underpowered_fixture,
)

RAW = HERE / "probe1-underpowered.raw.json"


def _flag(result: dict, fid: str) -> dict:
    for item in result["flags"]:
        if item["id"] == fid:
            return item
    raise SystemExit(f"FAILED:IMP-0251-probe1 missing flag {fid}")


def main() -> int:
    library = load_library()
    if set(library) != {
        "bp.experiment-design",
        "bp.statistical-review",
        "bp.scientific-replication",
        "bp.model-evaluation",
    }:
        print("FAILED:IMP-0251-probe1 library ids", sorted(library))
        return 1
    reasons = omission_gate()
    if len(reasons) != 6:
        print("FAILED:IMP-0251-probe1 omission gate", reasons)
        return 1

    weak = review(underpowered_fixture())
    strong = review(powered_fixture())
    bare = review(missing_effect_size_fixture())

    weak_under = _flag(weak, "underpowered")
    strong_under = _flag(strong, "underpowered")
    if not weak_under["flagged"]:
        print("FAILED:IMP-0251-probe1 underpowered not flagged", json.dumps(weak))
        return 1
    if strong_under["flagged"]:
        print("FAILED:IMP-0251-probe1 powered false-positive", json.dumps(strong))
        return 1
    if weak["power"] is None or not (weak["power"] < float(weak["threshold"]["min_power"])):
        print("FAILED:IMP-0251-probe1 underpowered power not below min_power", weak)
        return 1
    if not (strong["power"] >= float(strong["threshold"]["min_power"])):
        print("FAILED:IMP-0251-probe1 powered power below min_power", strong)
        return 1

    bare_es = _flag(bare, "missing-effect-size")
    strong_es = _flag(strong, "missing-effect-size")
    if not bare_es["flagged"]:
        print("FAILED:IMP-0251-probe1 missing effect size not flagged", json.dumps(bare))
        return 1
    if strong_es["flagged"]:
        print("FAILED:IMP-0251-probe1 effect-size false-positive", json.dumps(strong))
        return 1

    refused = False
    try:
        review(powered_fixture(), threshold_override=0.99)
    except PerRunThresholdTuneError:
        refused = True
    if not refused:
        print("FAILED:IMP-0251-probe1 per-run power threshold accepted")
        return 1

    spec = load_thresholds()
    doc = {
        "adequately_powered_underpowered_flag": False,
        "both_states": True,
        "min_power": spec["min_power"],
        "missing_effect_size_flagged": True,
        "omission_reason_ids": reasons,
        "pass": True,
        "powered_flagged": strong["flagged"],
        "powered_power": strong["power"],
        "threshold_id": spec["id"],
        "underpowered_flagged": True,
        "underpowered_power": weak["power"],
        "with_effect_size_missing_flag": False,
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"underpowered_flagged=True underpowered_power={weak['power']} "
        f"powered_under_flagged=False powered_power={strong['power']} "
        f"missing_effect_size_flagged=True min_power={spec['min_power']}"
    )
    print("SUCCESS:IMP-0251-probe1 underpowered flagged; powered silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
