#!/usr/bin/env python3
"""Probe 1: both invocations on the same commit; fresh-venv, not editable.

Reports both commands verbatim with exit codes and collected counts.
Equal exit codes with different collected counts are divergence, not parity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from testinfra.test_entry_parity import evaluate_good_path  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0333.json"
SENTINEL = "SUCCESS:TST-0333"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    result = evaluate_good_path(REPO)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:TST-0333-probe1 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0333-probe1 sentinel-absent")
            return 1
    if not result.get("pass"):
        print("FAILED:TST-0333-probe1 both-invocations / fresh-venv")
        return 1
    tests = {t["id"]: t for t in result.get("tests") or []}
    t1 = tests.get("test_both_invocations_same_commit") or {}
    t2 = tests.get("test_fresh_venv_not_editable") or {}
    print(
        f"module_exit={t1.get('module_exit_code')} "
        f"console_exit={t1.get('console_exit_code')} "
        f"module_collected={t1.get('module_collected')} "
        f"console_collected={t1.get('console_collected')} "
        f"not_editable={t2.get('not_editable')}"
    )
    print("SUCCESS:TST-0333-probe1 both invocations match; fresh venv is not editable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
