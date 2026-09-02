#!/usr/bin/env python3
"""Named probe 1: retrievability gate + version-string disqualification.

Re-runs T1 and T2 live. Checks the catalog receipt recorded both controls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import drill as D  # noqa: E402

ART = REPO / "command-center/receipts/REL-0006.json"


def main() -> int:
    t1 = D.test_corrupt_blocks()
    t2 = D.test_version_string_is_not_acceptance()
    print(json.dumps({"t1": t1, "t2": t2}, indent=2, sort_keys=True))
    if t1.get("result") != "PASS":
        print("FAILED:REL-0006-probe1 corrupt-n1 gate did not block")
        return 1
    if t2.get("result") != "PASS":
        print("FAILED:REL-0006-probe1 version-string was not disqualified")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:REL-0006-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "REL-0006":
        print("FAILED:REL-0006-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:REL-0006-probe1 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:REL-0006" not in text:
        print("FAILED:REL-0006-probe1 sentinel absent")
        return 1
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if tests.get("T1-corrupt-n1-blocks-before-downgrade", {}).get("result") != "PASS":
        print("FAILED:REL-0006-probe1 receipt T1 not PASS")
        return 1
    if tests.get("T2-version-string-reports-n1-behaviour-still-n", {}).get("result") != "PASS":
        print("FAILED:REL-0006-probe1 receipt T2 not PASS")
        return 1
    retr = doc.get("retrievability") or {}
    if not retr.get("corrupt_control_blocked"):
        print("FAILED:REL-0006-probe1 receipt missing corrupt_control_blocked")
        return 1
    print("blocked=True version_disqualified=True")
    print("SUCCESS:REL-0006-probe1 retrievability gate and version-string control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
