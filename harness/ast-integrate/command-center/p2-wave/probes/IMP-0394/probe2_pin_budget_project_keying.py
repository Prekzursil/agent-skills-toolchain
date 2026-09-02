#!/usr/bin/env python3
"""Probe 2: pin survives the IMP-0392 ceiling; per-project overrides do not leak.

Two instruments:
  * score-only fill of the same ceiling (control) drops the low-score pin
  * override-aware fill keeps the pin
  * project-a pin/ban vs project-b session keying (sibling isolation)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0394-probe2 {msg}")
    return 1


def main() -> int:
    S.require_receipt()
    pin = S.measure_pin_survives_budget()
    keying = S.measure_project_keying()
    print(
        json.dumps(
            {
                "probe": "probe2-pin-budget-project-keying",
                "unit_id": "IMP-0394",
                "pin": pin,
                "keying": keying,
                "pass": pin["pass"] and keying["pass"],
            },
            sort_keys=True,
        )
    )
    if not pin["pass"]:
        return fail("pin-survives-budget did not pass")
    if pin["pin_in_score_only_admitted"]:
        return fail("control path admitted the low-score pin; ceiling is inert")
    if not pin["pin_in_override_admitted"]:
        return fail("pinned capability dropped by IMP-0392 ceiling")
    if not keying["pass"]:
        return fail("per-project override leaked into sibling project")
    if keying["proj_pin_in_b"]:
        return fail("project-a pin leaked into project-b")
    if keying["proj_ban_in_a"]:
        return fail("project-a ban failed to exclude")
    if not keying["proj_ban_in_b"]:
        return fail("project-a ban leaked into project-b (sibling cannot admit)")
    print(
        "pin_survives_budget=True score_only_drops_pin=True "
        "sibling_project_isolated=True"
    )
    print("SUCCESS:IMP-0394-probe2 pin survives ceiling; project keying holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
