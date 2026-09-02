#!/usr/bin/env python3
"""Probe 1: injection corpus per-class catch rate.

A class with zero catches is P1. Mention controls must not be treated as
uses. Recorded rates in SECURITY.json must match this live run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as CORP  # noqa: E402

ART = REPO / "command-center/phase3/A6/SECURITY.json"
CLASSES = ("role-spoof", "instruction-override", "encoded")


def main() -> int:
    live = CORP.run_corpus()
    printable = {k: live[k] for k in sorted(live) if k != "rows"}
    print(json.dumps(printable, sort_keys=True))
    if not live.get("pass"):
        print("FAILED:ARC-0041-probe1 corpus did not pass")
        return 1
    if live["p1_zero_catch_classes"]:
        print(f"FAILED:ARC-0041-probe1 P1 zero-catch {live['p1_zero_catch_classes']}")
        return 1
    if live["mention_false_positives"] != 0:
        print("FAILED:ARC-0041-probe1 mention treated as use")
        return 1
    for cls in CLASSES:
        row = (live.get("per_class") or {}).get(cls) or {}
        if int(row.get("caught") or 0) < 1:
            print(f"FAILED:ARC-0041-probe1 class {cls} zero catches")
            return 1

    if not ART.is_file():
        print("FAILED:ARC-0041-probe1 SECURITY.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0041-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0041" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0041-probe1 sentinel absent")
        return 1
    rec = doc.get("injection_corpus") or {}
    if rec.get("computed_not_asserted") is not True:
        print("FAILED:ARC-0041-probe1 corpus not computed")
        return 1
    rec_pc = rec.get("per_class") or {}
    for cls in CLASSES:
        live_c = int(live["per_class"][cls]["caught"])
        rec_c = int((rec_pc.get(cls) or {}).get("caught") or -1)
        if live_c != rec_c:
            print(f"FAILED:ARC-0041-probe1 {cls} caught live={live_c} rec={rec_c}")
            return 1
    if list(rec.get("p1_zero_catch_classes") or []) != list(live["p1_zero_catch_classes"]):
        print("FAILED:ARC-0041-probe1 recorded P1 classes drifted")
        return 1
    rec_fp = rec.get("mention_false_positives")
    if rec_fp is None or int(rec_fp) != int(live["mention_false_positives"]):
        print("FAILED:ARC-0041-probe1 mention FP drifted")
        return 1
    print(
        "per_class="
        + ",".join(
            f"{c}:{live['per_class'][c]['caught']}/{live['per_class'][c]['n']}"
            for c in CLASSES
        )
        + f" mention_fp={live['mention_false_positives']}"
    )
    print("SUCCESS:ARC-0041-probe1 injection corpus per-class catch rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
