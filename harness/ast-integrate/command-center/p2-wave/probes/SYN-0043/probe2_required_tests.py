#!/usr/bin/env python3
"""Named probe 2: re-run the four catalog tests_required on the evaluator.

Independent of the artifact's stored overall_verdict. Includes the planted
condition-4 false and the single-NOT-CHECKED aggregation control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from evaluate import run_required_tests  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0043.stopping-verdict.json"
SENTINEL = "SUCCESS:SYN-0043"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:SYN-0043-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "SYN-0043":
        print("FAILED:SYN-0043-probe2 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in text:
        print("FAILED:SYN-0043-probe2 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:SYN-0043-probe2 self-declared", st)
        return 1

    tests = run_required_tests()
    failed = [t for t in tests if t["verdict"] != "PASS"]
    payload = {
        "failed": len(failed),
        "pass": not failed,
        "probe": "probe2-required-tests",
        "tests": tests,
        "unit_id": "SYN-0043",
    }
    print(json.dumps(payload, sort_keys=True))
    if failed:
        print("FAILED:SYN-0043-probe2 required tests")
        return 1
    stored = {}
    for t in doc.get("tests") or []:
        if isinstance(t, dict) and t.get("id"):
            stored[t["id"]] = t.get("result") or t.get("verdict")
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    for t in report.get("catalog_tests") or []:
        if isinstance(t, dict) and t.get("id") and t["id"] not in stored:
            stored[t["id"]] = t.get("verdict")
    for t in tests:
        if stored.get(t["id"]) != "PASS":
            print(f"FAILED:SYN-0043-probe2 artifact test row {t['id']} not PASS")
            return 1
    print("required_tests PASS=4 planted_c4_flips=True not_checked_blocks=True")
    print("SUCCESS:SYN-0043-probe2 required tests including planted C4 and NOT-CHECKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
