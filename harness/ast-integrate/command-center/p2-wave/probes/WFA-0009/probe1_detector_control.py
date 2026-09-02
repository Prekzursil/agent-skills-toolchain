#!/usr/bin/env python3
"""Probe 1: detector control BEFORE any sweep result is read.

known-present -> HIT
known-absent  -> MISS
empty file    -> PRESENT-EMPTY, never HIT
decoy .md     -> not workflow-bearing
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import estate as E  # noqa: E402
import reconcile as R  # noqa: E402

OUT = HERE / "probe1-detector-control.raw.json"


def broken_empty_as_hit(path: Path) -> str:
    """The failure class this control exists to catch."""
    if not path.exists():
        return "MISS"
    return "HIT"


def main() -> int:
    E.build_estate()
    present = R.classify_path(E.present_path())
    absent = R.classify_path(E.absent_path())
    empty = R.classify_path(E.empty_path())
    decoy_bearing, decoy_reason, _ = R.is_workflow_bearing(E.decoy_path(), E.DISK)

    if present["verdict"] != "HIT" or not present["bytes"]:
        print("FAILED:WFA-0009-probe1 known-present was not HIT")
        return 1
    if absent["verdict"] != "MISS":
        print("FAILED:WFA-0009-probe1 known-absent was not MISS")
        return 1
    if empty["verdict"] != "PRESENT-EMPTY":
        print(
            "FAILED:WFA-0009-probe1 empty path was "
            f"{empty['verdict']}, want PRESENT-EMPTY"
        )
        return 1
    if empty["verdict"] == "HIT":
        print("FAILED:WFA-0009-probe1 empty path classified as HIT")
        return 1
    if decoy_bearing:
        print(f"FAILED:WFA-0009-probe1 decoy .md counted as workflow ({decoy_reason})")
        return 1

    broken = broken_empty_as_hit(E.empty_path())
    if broken != "HIT":
        print("FAILED:WFA-0009-probe1 broken classifier did not produce HIT on empty")
        return 1
    if empty["verdict"] == broken:
        print("FAILED:WFA-0009-probe1 live classifier matches the empty-as-HIT mutant")
        return 1

    doc = {
        "pass": True,
        "sweep_read": False,
        "known_present": present,
        "known_absent": absent,
        "present_empty": empty,
        "decoy_not_bearing": True,
        "decoy_reason": decoy_reason,
        "empty_as_hit_mutant_verdict": broken,
        "empty_as_hit_mutant_rejected": True,
        "control_ran_before_sweep": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "present=HIT absent=MISS empty=PRESENT-EMPTY decoy_not_bearing=True "
        "sweep_read=False empty_as_hit_mutant_rejected=True"
    )
    print("SUCCESS:WFA-0009-probe1 detector control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
