#!/usr/bin/env python3
"""probe1 for TST-0010: an OPEN P1 on an otherwise-complete candidate blocks.

Runs the live tools/command-center/completion_c10.py C10 evaluator, asserts the
block names the defect id and failing_condition_id=10, and writes the block
transcript fixture consumed by the receipt.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0010"
FIX = Path(__file__).resolve().parent / "fixtures"


def load_c10():
    spec = importlib.util.spec_from_file_location(
        "completion_c10_live", REPO / "tools" / "command-center" / "completion_c10.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["completion_c10_live"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    c10 = load_c10()
    checks = {}
    cand = c10.isolation_candidate()
    cand = dict(cand)
    cand["defects"] = [{"id": "D-BLOCK-1", "severity": "P1", "status": "open"}]
    res = c10.evaluate_c10(cand, [])
    checks["open_p1_blocks"] = res["outcome"] == "UNSATISFIED"
    checks["names_defect_id"] = "D-BLOCK-1" in (res.get("named_defect_ids") or [])
    checks["failing_condition_id_10"] = res.get("failing_condition_id") == 10
    transcript = {
        "unit_id": UID,
        "verdict": res["outcome"],
        "failing_condition_id": res.get("failing_condition_id"),
        "named_defect_ids": res.get("named_defect_ids"),
        "basis": res.get("basis"),
        "condition_text": res.get("text"),
    }
    FIX.mkdir(parents=True, exist_ok=True)
    out = FIX / "blocked_open_p1.transcript.txt"
    out.write_text(json.dumps(transcript, indent=1) + "\n", encoding="utf-8", newline="\n")
    checks["transcript_written"] = out.stat().st_size > 0
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({"unit_id": UID, "probe": "probe1-open-p1-blocks", "pass": ok, "checks": checks, "transcript": transcript}))
    if ok:
        print("SUCCESS:" + UID + "-probe1 open P1 blocks a complete candidate; block names D-BLOCK-1 and failing_condition_id=10")
        return 0
    print("FAILED:" + UID + "-probe1 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
