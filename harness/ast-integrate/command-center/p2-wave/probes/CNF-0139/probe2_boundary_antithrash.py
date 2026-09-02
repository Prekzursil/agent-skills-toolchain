#!/usr/bin/env python3
"""Probe 2: boundary, anti-thrash, BLOCKED denominator control, reviewer slips."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONF = REPO / "command-center" / "confirmation"
sys.path.insert(0, str(CONF))

from expansion_proof import (  # noqa: E402
    antithrash,
    boundary,
    denominator_control,
    reviewer_slip_attempts,
)

ART = REPO / "command-center/receipts/CNF-0139.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0139-p2-") as tmp:
        root = Path(tmp)
        b = boundary(REPO, root / "boundary")
        a = antithrash(REPO, root / "antithrash")
        d = denominator_control(REPO, root / "denominator")
        r = reviewer_slip_attempts(REPO, root / "reviewer")
    summary = {
        "probe": "probe2-boundary-antithrash-denominator",
        "boundary_pass": b["pass"],
        "boundary_reason": b["at_threshold"]["reason"],
        "antithrash_pass": a["pass"],
        "antithrash_second_reason": a["second"]["reason"],
        "denominator_pass": d["pass"],
        "denominator_changes_decision": d["decision_changes"],
        "reviewer_pass": r["pass"],
    }
    print(json.dumps(summary, sort_keys=True))
    if not b["pass"]:
        print("FAILED:CNF-0139-probe2 boundary")
        return 1
    if b["at_threshold"]["reason"] != "at_threshold":
        print("FAILED:CNF-0139-probe2 equality not classified as at_threshold")
        return 1
    if not a["pass"] or a["second"]["queue_length_delta"] != 0:
        print("FAILED:CNF-0139-probe2 anti-thrash")
        return 1
    if not d["pass"] or not d["decision_changes"]:
        print("FAILED:CNF-0139-probe2 denominator control")
        return 1
    if not r["pass"]:
        print("FAILED:CNF-0139-probe2 reviewer")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0139-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    tests = doc.get("tests") or {}
    if not (tests.get("boundary") or {}).get("pass"):
        print("FAILED:CNF-0139-probe2 receipt boundary not pass")
        return 1
    if not (tests.get("anti_thrash") or {}).get("pass"):
        print("FAILED:CNF-0139-probe2 receipt anti-thrash not pass")
        return 1
    if not (tests.get("denominator_control") or {}).get("pass"):
        print("FAILED:CNF-0139-probe2 receipt denominator not pass")
        return 1
    if "SUCCESS:CNF-0139" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0139-probe2 sentinel absent")
        return 1
    print("SUCCESS:CNF-0139-probe2 boundary anti-thrash denominator reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
