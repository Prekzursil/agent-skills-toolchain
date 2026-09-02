#!/usr/bin/env python3
"""Probe 1: enumerator finds a known-present planted detector (census control).

Known-present runs first. An empty tree may report zero only after that
control has FIRED. A silent-in-both-states enumerator is rejected.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from detector_control.enumerate import (  # noqa: E402
    PLANTED_IDS,
    enumerate_detectors,
    enumerator_control,
)

UNIT = "TST-0014"


def test_enumerator_finds_a_known_detector() -> dict:
    """Catalog test: detector control on the detector census."""
    control = enumerator_control()
    if not control["fired"]:
        return {
            "id": "test_enumerator_finds_a_known_detector",
            "pass": False,
            "reason": "enumerator missed planted detectors",
            "control": control,
        }
    empty = Path(tempfile.mkdtemp(prefix="tst0014-empty-"))
    negative = enumerator_control(empty)
    live = enumerate_detectors(REPO, skip_self_fixtures=True)
    live_ids = [d.id for d in live]
    kinds = {d.kind for d in live}
    ok = (
        control["known_present_run_first"] is True
        and control["fired_before_absence_reported"] is True
        and set(control["found_planted"]) == set(PLANTED_IDS)
        and not control["missing_planted"]
        and negative["fired"] is False
        and set(negative["missing_planted"]) == set(PLANTED_IDS)
        and len(live) >= 1
        and "validator_rule" in kinds
        and "hook_check" in kinds
        and "gate_script" in kinds
        and "REACH-1" in live_ids
    )
    return {
        "id": "test_enumerator_finds_a_known_detector",
        "pass": ok,
        "control_fired": control["fired"],
        "found_planted": control["found_planted"],
        "negative_fired": negative["fired"],
        "negative_missing": negative["missing_planted"],
        "live_count": len(live),
        "live_ids": live_ids,
        "kinds": sorted(kinds),
        "known_present_run_first": True,
        "fired_before_absence_reported": True,
    }


def main() -> int:
    result = test_enumerator_finds_a_known_detector()
    payload = {
        "probe": "probe1-enumerator-finds-known",
        "unit_id": UNIT,
        "pass": result["pass"],
        **{k: v for k, v in result.items() if k != "pass"},
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"control_fired={result['control_fired']} "
        f"negative_fired={result['negative_fired']} "
        f"live_count={result['live_count']} "
        f"known_present_run_first=True"
    )
    if not result["pass"]:
        print("FAILED:TST-0014-probe1 enumerator did not find known-present detector")
        return 1
    print("SUCCESS:TST-0014-probe1 enumerator finds known-present detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
