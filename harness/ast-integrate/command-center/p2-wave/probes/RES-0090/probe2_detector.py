#!/usr/bin/env python3
"""Probe 2: independent reviewer — detector silent on known-good, fires on known-broken."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lib import (  # noqa: E402
    apply_operator,
    detector,
    load_operators,
    original_hook_source,
)

ART = REPO / "command-center" / "research" / "RES-0090.json"
SENTINEL = (
    "SUCCESS:RES-0090 in the receipt AND a pre-published operator set plus a "
    "measured survival rate on one real hook with a killed control"
)


def main() -> int:
    ops = load_operators()
    control = next(o for o in ops["operators"] if o["id"] == ops["control_operator_id"])
    good_src = original_hook_source()
    broken_src = apply_operator(good_src, control)

    good = detector(good_src)
    broken = detector(broken_src)
    if good["fired"]:
        print("FAILED:RES-0090-probe2 detector fired on known-good original hook")
        return 1
    if not broken["fired"]:
        print("FAILED:RES-0090-probe2 detector silent on known-broken never-fire mutant")
        return 1
    if good["fired"] == broken["fired"]:
        print("FAILED:RES-0090-probe2 silent-in-both-states")
        return 1

    if not ART.is_file():
        print("FAILED:RES-0090-probe2 artifact missing")
        return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    blob = ART.read_text(encoding="utf-8")
    if SENTINEL not in blob:
        print("FAILED:RES-0090-probe2 catalog sentinel absent")
        return 1
    runs = art.get("detector_runs") or {}
    kg = runs.get("known_good") or {}
    kb = runs.get("known_broken") or {}
    if kg.get("fired") is not False:
        print("FAILED:RES-0090-probe2 artifact known_good.fired is not false")
        return 1
    if kb.get("fired") is not True:
        print("FAILED:RES-0090-probe2 artifact known_broken.fired is not true")
        return 1

    payload = {
        "probe": "probe2-detector",
        "known_good_fired": good["fired"],
        "known_broken_fired": broken["fired"],
        "known_good_failures": good["oracle"]["failures"],
        "known_broken_failures": broken["oracle"]["failures"],
        "reviewer_id": "RES-0090-probe2-both-fixture-rerun",
        "independent": True,
        "verdict": "PASS",
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"known_good_fired={good['fired']} known_broken_fired={broken['fired']} "
        f"broken_failures={broken['oracle']['failures']}"
    )
    print("SUCCESS:RES-0090-probe2 detector silent on good, fires on broken")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
