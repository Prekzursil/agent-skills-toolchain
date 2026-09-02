#!/usr/bin/env python3
"""Probe 2: remove the console-script entry point.

The console-script arm fails; the python -m arm still passes. Both-states
control is silent on the good package and fires on the stripped wheel.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from testinfra.test_entry_parity import (  # noqa: E402
    test_break_entry_point_console_fails_module_passes,
)

ART = REPO / "command-center" / "receipts" / "TST-0333.json"
SENTINEL = "SUCCESS:TST-0333"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    result = test_break_entry_point_console_fails_module_passes(REPO)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:TST-0333-probe2 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0333-probe2 sentinel-absent")
            return 1
    if not result.get("pass"):
        print("FAILED:TST-0333-probe2 break-entry-point control")
        return 1
    verbatim = result.get("verbatim") or {}
    good = verbatim.get("good") or {}
    broken = verbatim.get("broken") or {}
    print(
        f"good console_exit={good.get('console_exit_code')} "
        f"collected={good.get('console_collected')} "
        f"broken console_exit={broken.get('console_exit_code')} "
        f"module still {broken.get('module_exit_code')} "
        f"collected={broken.get('module_collected')}"
    )
    print(
        "SUCCESS:TST-0333-probe2 missing entry point fails console-script; "
        "python -m still passes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
