#!/usr/bin/env python3
"""Probe 2: scanner flags a planted inert detector and does not flag a known-good one."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scanner import (  # noqa: E402
    known_good_adapter,
    planted_inert_adapter,
    scan,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0018-probe2 {msg}")
    return 1


def main() -> int:
    planted = planted_inert_adapter()
    good = known_good_adapter()
    result = scan(extra=[planted, good])
    extras = {r["detector_id"]: r for r in result["extra_rows"]}
    plant = extras.get(planted.detector_id)
    control = extras.get(good.detector_id)
    payload = {
        "planted": plant,
        "known_good": control,
        "planted_flagged_inert": bool(plant and plant.get("inert")),
        "known_good_flagged_inert": bool(control and control.get("inert")),
        "pass": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))

    if plant is None:
        return fail("planted inert detector missing from extra rows")
    if not plant.get("inert"):
        return fail(
            f"scanner did not flag planted inert detector (verdict={plant.get('verdict')})"
        )
    if control is None:
        return fail("known-good detector missing from extra rows")
    if control.get("inert"):
        return fail(
            f"scanner flagged known-good detector as INERT (verdict={control.get('verdict')})"
        )
    if control.get("verdict") != "DIFFERS":
        return fail(f"known-good detector verdict {control.get('verdict')} != DIFFERS")

    print(
        "planted_inert_flagged known_good_not_flagged "
        f"planted_verdict={plant['verdict']} good_verdict={control['verdict']}"
    )
    print("SUCCESS:TST-0018-probe2 planted inert flagged; known-good not flagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
