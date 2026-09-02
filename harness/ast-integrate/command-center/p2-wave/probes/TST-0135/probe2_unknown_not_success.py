#!/usr/bin/env python3
"""TST-0135 probe 2: missing ledger is UNKNOWN, not SUCCESS (independent reviewer)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if not (REPO / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
    REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(REPO / "tools" / "command-center" / "tests"))

from test_codex_mcp_recovery import run_negative_suite  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0135.json"
SENTINEL = "SUCCESS:TST-0135"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    result = run_negative_suite()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:TST-0135-probe2 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0135-probe2 sentinel-absent")
            return 1
    control = result.get("two_state") or {}
    honest = result.get("honest_missing_ledger") or {}
    if not result.get("pass"):
        print("FAILED:TST-0135-probe2 missing-ledger UNKNOWN")
        return 1
    if honest.get("named_outcome") != "UNKNOWN":
        print("FAILED:TST-0135-probe2 honest path was not UNKNOWN")
        return 1
    if honest.get("state") == "SUCCESS" or honest.get("success") is True:
        print("FAILED:TST-0135-probe2 honest missing ledger reported SUCCESS")
        return 1
    if control.get("verdict") != "DIFFERS":
        print("FAILED:TST-0135-probe2 mutant did not discriminate")
        return 1
    present = result.get("present_ledger") or {}
    if present.get("state") != "SUCCESS":
        print("FAILED:TST-0135-probe2 present ledger was not SUCCESS")
        return 1
    print(
        f"honest={honest.get('named_outcome')}/{honest.get('state')} "
        f"present={present.get('named_outcome')} "
        f"mutant_two_state={control.get('verdict')}"
    )
    print("SUCCESS:TST-0135-probe2 deleting ledger reports UNKNOWN not SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
