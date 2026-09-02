#!/usr/bin/env python3
"""Probe 2: DETECTOR CONTROL — planted unmanifested file must be reported.

Also requires the clean fixture to stay silent so the detector is not a
always-fire alarm.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WALKER_PATH = HERE / "walker.py"


def load_walker():
    spec = importlib.util.spec_from_file_location("cnf0122_walker2", WALKER_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit("FAILED:CNF-0122-probe2 cannot load walker.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cnf0122_walker2"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    walker = load_walker()
    broken = walker.run_unmanifested_control()
    planted = broken["planted_path"]
    if not broken.get("reported"):
        print(
            "FAILED:CNF-0122-probe2 planted unmanifested file not reported: "
            + planted
            + " unmanifested="
            + json.dumps(broken["unmanifested_paths"])
        )
        return 1
    if planted not in broken["unmanifested_paths"]:
        print("FAILED:CNF-0122-probe2 planted path missing from unmanifested list")
        return 1
    if broken["expected_matching"] in broken["unmanifested_paths"]:
        print("FAILED:CNF-0122-probe2 manifested matching file listed as unmanifested")
        return 1

    clean = walker.run_clean_control()
    if not clean.get("silent_on_clean"):
        print(
            "FAILED:CNF-0122-probe2 clean fixture was not silent: "
            + json.dumps(
                {
                    "unmanifested": clean["unmanifested_paths"],
                    "absent": clean["absent_paths"],
                    "mismatches": clean["hash_mismatch_paths"],
                }
            )
        )
        return 1
    print(
        json.dumps(
            {
                "planted_path": planted,
                "reported": True,
                "fired_on_broken": True,
                "silent_on_clean": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0122-probe2 unmanifested-file control fired; clean fixture silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
