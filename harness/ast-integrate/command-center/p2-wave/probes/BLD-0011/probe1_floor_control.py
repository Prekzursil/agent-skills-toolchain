#!/usr/bin/env python3
"""Named probe 1: floor subset + newer-syntax control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402

ART = M.REPO / M.OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:BLD-0011-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "BLD-0011":
        print("FAILED:BLD-0011-probe1 unit_id", doc.get("unit_id"))
        return 1
    blob = json.dumps(doc)
    if "SUCCESS:BLD-0011" not in blob:
        print("FAILED:BLD-0011-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:BLD-0011-probe1 self-declared", doc.get("state"))
        return 1

    raw = M.run_campaign()
    if not raw.get("good_pass"):
        print("FAILED:BLD-0011-probe1 floor subset did not pass")
        print((raw.get("good") or {}).get("output", "")[-1500:])
        return 1
    if not raw.get("caught"):
        print("FAILED:BLD-0011-probe1 newer syntax not caught at floor")
        print((raw.get("mutant") or {}).get("output", "")[-1500:])
        return 1
    control = doc.get("control") or {}
    if control.get("floor_caught") is not True:
        print("FAILED:BLD-0011-probe1 artifact control.floor_caught is not true")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-floor-control",
                "unit_id": "BLD-0011",
                "pass": True,
                "floor_mode": raw.get("floor_mode"),
                "floor_label": raw.get("floor_label"),
                "good_pass": raw.get("good_pass"),
                "caught": raw.get("caught"),
                "mut_name": raw.get("mut_name"),
                "interp_caught": raw.get("interp_caught"),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:BLD-0011-probe1 floor subset and newer-syntax control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
