#!/usr/bin/env python3
"""IMP-0453 probe 1: kill-late partial survives, INCOMPLETE, ledger-referenced."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(REPO / "tools" / "command-center" / "tests"))

from test_partial_preserve import run_kill_late_suite  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0453.json"
SENTINEL = "SENTINEL:IMP-0453:PARTIALS-PRESERVED"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    result = run_kill_late_suite()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:IMP-0453-probe1 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:IMP-0453-probe1 sentinel-absent")
            return 1
    if not result.get("pass"):
        print("FAILED:IMP-0453-probe1 kill-late partial did not survive as INCOMPLETE")
        return 1
    print(
        f"bytes={result.get('bytes')} classification={result.get('classification')} "
        f"ledger_referenced={result.get('ledger_referenced')} "
        f"same_inode={result.get('same_inode')}"
    )
    print("SUCCESS:IMP-0453-probe1 kill-late partial preserved and classified INCOMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
