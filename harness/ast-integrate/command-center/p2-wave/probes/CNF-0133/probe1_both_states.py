#!/usr/bin/env python3
"""Probe 1: live both-states, leakage, blind form, naive hazard, artifact sentinel."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from calibrate import run_calibration, tests_pass  # noqa: E402
from pipeline import claim_form_ok, scan_leakage  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0133.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0133-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0133":
        print("FAILED:CNF-0133-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0133-probe1 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:CNF-0133" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0133-probe1 sentinel absent")
        return 1

    cal = run_calibration()
    if not tests_pass(cal):
        print("FAILED:CNF-0133-probe1 live calibration tests")
        print(json.dumps(cal["tests"], indent=2)[:2000])
        return 1

    bs = cal["both_states"]["combined"]
    print(
        "both_states true_confirmed="
        f"{bs['planted_true_confirmed']} false_refuted={bs['planted_false_refuted']}"
    )
    if not bs["pass"]:
        print("FAILED:CNF-0133-probe1 both-states failed")
        return 1

    if cal["leakage_tokens_found"]:
        print("FAILED:CNF-0133-probe1 leakage", cal["leakage_tokens_found"])
        return 1

    live_ids = {r["claim_id"] for r in cal["combined_rows"]}
    art_ids = {r["claim_id"] for r in doc.get("planted_items") or []}
    if live_ids != art_ids:
        print("FAILED:CNF-0133-probe1 planted id mismatch")
        print("only_live", sorted(live_ids - art_ids)[:8])
        print("only_art", sorted(art_ids - live_ids)[:8])
        return 1

    live_m = cal["combined_matrix"]
    art_m = doc.get("confusion_matrix") or {}
    for k in ("true_positive", "false_positive", "false_negative", "true_negative"):
        if live_m.get(k) != art_m.get(k):
            print(f"FAILED:CNF-0133-probe1 matrix {k} live={live_m.get(k)} art={art_m.get(k)}")
            return 1

    inbox = []
    for sid in ("set_a", "set_b"):
        for c in cal["plants"][sid]["claims"]:
            inbox.append(json.dumps(c, sort_keys=True))
        for subj in cal["plants"][sid]["subjects"].values():
            inbox.append(json.dumps(subj, sort_keys=True))
    leaks = scan_leakage(inbox)
    if leaks:
        print("FAILED:CNF-0133-probe1 inbox leakage", leaks)
        return 1
    form_ok, why = claim_form_ok(cal["plants"]["set_a"]["claims"])
    print(f"blind_form={form_ok} {why}")
    if not form_ok:
        print("FAILED:CNF-0133-probe1 form check")
        return 1

    naive = cal["runs"]["set_a"]["naive_false_pass"]
    if naive["numerator"] != naive["denominator"] or naive["denominator"] < 1:
        print("FAILED:CNF-0133-probe1 naive control did not false-pass planted-false")
        return 1

    tests = {t["id"]: t["result"] for t in doc.get("tests") or []}
    for tid in ("blind-form", "both-states", "leakage-control", "rerun-stability"):
        if tests.get(tid) != "PASS":
            print(f"FAILED:CNF-0133-probe1 artifact test {tid}={tests.get(tid)}")
            return 1

    print("SUCCESS:CNF-0133-probe1 both-states leakage blind naive-hazard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
