#!/usr/bin/env python3
"""TST-0171 probe 1: clean shutdown always registers; crash window is a real orphan."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(REPO / "tools" / "command-center" / "tests"))

from test_orphan_resume import run_clean_shutdown_suite  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0171.json"
SENTINEL = "SUCCESS:TST-0171"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    result = run_clean_shutdown_suite()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:TST-0171-probe1 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0171-probe1 sentinel-absent")
            return 1
    both = result.get("both_states") or {}
    if not result.get("pass"):
        print("FAILED:TST-0171-probe1 clean-shutdown / crash-window")
        return 1
    if not both.get("clean_always_registers"):
        print("FAILED:TST-0171-probe1 clean publish did not always register")
        return 1
    if not both.get("crash_without_resume_is_orphan"):
        print("FAILED:TST-0171-probe1 crash window is not an orphan")
        return 1
    print(
        f"clean_all_registered={both.get('clean_always_registers')} "
        f"window_orphan={both.get('crash_without_resume_is_orphan')} "
        f"resume_resolves={both.get('resume_resolves_orphan')}"
    )
    print("SUCCESS:TST-0171-probe1 clean shutdown always registers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
