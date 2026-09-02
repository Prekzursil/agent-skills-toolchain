#!/usr/bin/env python3
"""Named probe 1: every table row graded with effect+baseline; E3 both-states."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catalog as C  # noqa: E402
import grade as G  # noqa: E402

ART = REPO / "command-center/research/RES-0077.json"
SENTINEL = (
    "SUCCESS:RES-0077 in the receipt AND a bias-by-correction table with "
    "per-row effect sizes and an explicit grade"
)


def main() -> int:
    errs = G.grade_errors()
    if errs:
        print("FAILED:RES-0077-probe1 grade_errors")
        print(json.dumps(errs, indent=2)[:4000])
        return 1
    ctrl = G.both_states_headline_without_baseline()
    print(
        f"headline_control ok={ctrl['ok']} silent_on_good={ctrl['silent_on_good']} "
        f"fires_on_bad={ctrl['fires_on_bad']} good_id={ctrl['good_id']} "
        f"bad_tier={ctrl['bad_tier']}"
    )
    if not ctrl["ok"]:
        print("FAILED:RES-0077-probe1 E3 headline control did not discriminate")
        print(json.dumps(ctrl, indent=2))
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0077-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:RES-0077-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:RES-0077-probe1 sentinel absent")
        return 1
    if text.find('"grading_rule"') > text.find('"bias_by_correction_table"'):
        print("FAILED:RES-0077-probe1 grading_rule not stated before table")
        return 1
    table = doc.get("bias_by_correction_table") or []
    if len(table) < 8:
        print(f"FAILED:RES-0077-probe1 table too small n={len(table)}")
        return 1
    live = {r["id"]: r for r in G.live_table()}
    for row in table:
        rid = row.get("id")
        if rid not in live:
            print(f"FAILED:RES-0077-probe1 artifact row {rid} not in live table")
            return 1
        if row.get("grade") not in C.GRADES:
            print(f"FAILED:RES-0077-probe1 {rid} grade {row.get('grade')}")
            return 1
        if live[rid]["grade"] != row.get("grade"):
            print(f"FAILED:RES-0077-probe1 {rid} grade drift")
            return 1
        if G.empty(row.get("effect_size")) or G.empty(row.get("baseline")):
            print(f"FAILED:RES-0077-probe1 {rid} missing effect/baseline")
            return 1
        if G.empty(row.get("source")) or G.empty(row.get("locator")):
            print(f"FAILED:RES-0077-probe1 {rid} missing citation locator")
            return 1
    biases = {row.get("bias") for row in table}
    if set(C.BIASES) - biases:
        print(f"FAILED:RES-0077-probe1 missing biases {set(C.BIASES) - biases}")
        return 1
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    t1 = tests.get("T-grade-every-correction")
    if not t1 or t1.get("result") != "PASS":
        print("FAILED:RES-0077-probe1 artifact test T-grade-every-correction not PASS")
        return 1
    mechs = doc.get("mechanisms") or []
    if any(not m.get("promotable") for m in mechs):
        print("FAILED:RES-0077-probe1 a listed mechanism is not promotable")
        return 1
    if len(mechs) < 4:
        print("FAILED:RES-0077-probe1 need four named bias mechanisms")
        return 1
    print(f"table_rows={len(table)} mechanisms={len(mechs)} grades_ok=True")
    print("SUCCESS:RES-0077-probe1 table grades, citations, E3 both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
