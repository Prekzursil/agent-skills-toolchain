#!/usr/bin/env python3
"""TST-0135 probe 1: cancelled call is reclaimed or abandoned; uncancelled is normal."""

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

from test_codex_mcp_recovery import run_cancel_suite  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0135.json"
SENTINEL = "SUCCESS:TST-0135"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    result = run_cancel_suite()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:TST-0135-probe1 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0135-probe1 sentinel-absent")
            return 1
    both = result.get("both_states") or {}
    orphan = result.get("orphan_mutant") or {}
    if not result.get("pass"):
        print("FAILED:TST-0135-probe1 cancel/reclaim/abandon")
        return 1
    if both.get("verdict") != "DIFFERS":
        print("FAILED:TST-0135-probe1 uncancelled-vs-window did not differ")
        return 1
    if orphan.get("verdict") != "DIFFERS":
        print("FAILED:TST-0135-probe1 orphan mutant did not fire")
        return 1
    uncancelled = result.get("uncancelled") or {}
    if uncancelled.get("abandoned_record") is not False:
        print("FAILED:TST-0135-probe1 uncancelled produced ABANDONED")
        return 1
    reclaim = result.get("reclaim") or {}
    abandon = result.get("abandon") or {}
    if reclaim.get("named_outcome") != "RECLAIMED":
        print("FAILED:TST-0135-probe1 reclaim path not named RECLAIMED")
        return 1
    if abandon.get("named_outcome") != "ABANDONED":
        print("FAILED:TST-0135-probe1 abandon path not named ABANDONED")
        return 1
    print(
        f"uncancelled={uncancelled.get('named_outcome')} "
        f"reclaim={reclaim.get('named_outcome')} "
        f"abandon={abandon.get('named_outcome')} "
        f"both={both.get('verdict')} orphan_mutant={orphan.get('verdict')}"
    )
    print("SUCCESS:TST-0135-probe1 cancel recovers without orphan threads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
