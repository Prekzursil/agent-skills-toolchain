#!/usr/bin/env python3
"""Probe 1: known-nondeterministic timestamp control + both-states deterministic payload.

Live re-run of the two reproductions. Independent of probe 2 (over-normalization
and triple-run). If the receipt exists, also checks it recorded the same two
controls as PASS and carries SUCCESS:CNF-0184.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from audit import audit_one  # noqa: E402
from normalizers import CLASS_TIMESTAMPS, apply_one  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0184.json"


def main() -> int:
    ts = audit_one("fam3.iso-timestamp")
    det = audit_one("fam3.deterministic-payload")
    t1, t2 = ts["outputs"][0], ts["outputs"][1]
    ts_raw_diff = t1 != t2
    ts_norm_same = apply_one(CLASS_TIMESTAMPS, t1) == apply_one(CLASS_TIMESTAMPS, t2)
    det_same = det["outputs"][0] == det["outputs"][1]
    if not ts_raw_diff:
        print("FAILED:CNF-0184-probe1 timestamp reproduction did not vary")
        return 1
    if not ts_norm_same:
        print("FAILED:CNF-0184-probe1 timestamp normalizer did not equalize")
        return 1
    if CLASS_TIMESTAMPS not in ts["varying_classes"]:
        print("FAILED:CNF-0184-probe1 timestamps class not attributed")
        return 1
    if not det_same or det["classification"] != "BYTE-DETERMINISTIC":
        print("FAILED:CNF-0184-probe1 deterministic payload was not byte-identical")
        return 1
    if len(det["run_ids"]) < 2:
        print("FAILED:CNF-0184-probe1 deterministic run_ids missing")
        return 1

    if ART.is_file() and ART.stat().st_size > 200:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if "SUCCESS:CNF-0184" not in text:
            print("FAILED:CNF-0184-probe1 sentinel absent from receipt")
            return 1
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            print("FAILED:CNF-0184-probe1 self-declared", doc.get("state"))
            return 1
        tests = doc.get("tests") or {}
        if tests.get("known_nondeterministic_control", {}).get("pass") is not True:
            print("FAILED:CNF-0184-probe1 receipt known-nd control not PASS")
            return 1
        if tests.get("both_states", {}).get("pass") is not True:
            print("FAILED:CNF-0184-probe1 receipt both_states not PASS")
            return 1

    print(
        f"ts_raw_diff={ts_raw_diff} ts_norm_same={ts_norm_same} "
        f"det_raw_identical={det_same} det_runs={len(det['run_ids'])} "
        f"ts_classes={ts['varying_classes']}"
    )
    print("SUCCESS:CNF-0184-probe1 known-nondeterministic and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
