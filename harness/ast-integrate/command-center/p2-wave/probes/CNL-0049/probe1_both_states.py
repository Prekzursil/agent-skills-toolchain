#!/usr/bin/env python3
"""Probe 1: fake-steelman fails, genuine passes; both-states + negative control.

FIRES on planted-bad token concession; SILENT on known-good steelman.
Also records the check on the state it is meant to reject (token concession).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

FIX = HERE / "fixtures"
RAW = HERE / "probe1-both-states.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0049-probe1 {msg}")
    return 1


def main() -> int:
    genuine = D.evaluate_path(FIX / "genuine.json")
    fake = D.evaluate_path(FIX / "fake_token.json")
    label = D.evaluate_path(FIX / "fake_label.json")

    if genuine["fired"] or not genuine["silent"] or genuine["verdict"] != "PASS":
        return fail(f"genuine did not pass: {genuine}")
    if not genuine["coverage_ok"] or not genuine["ordering_ok"]:
        return fail(f"genuine signals incomplete: {genuine}")
    if genuine["covered_count"] != 3:
        return fail(f"genuine covered_count={genuine['covered_count']}")

    if not fake["fired"] or fake["silent"] or fake["verdict"] != "FAIL":
        return fail(f"token concession did not fail: {fake}")
    if fake["coverage_ok"]:
        return fail("token concession unexpectedly coverage_ok")

    if not label["fired"] or label["verdict"] != "FAIL":
        return fail(f"label-only steelman did not fail: {label}")

    # Negative control: state the check is meant to reject = token concession.
    negative = {
        "rejects": "token-concession-then-prepared-attack",
        "observed": "FIRES",
        "fired": fake["fired"],
        "verdict": fake["verdict"],
        "reasons": fake["reasons"],
        "missing_claim_ids": fake["missing_claim_ids"],
    }
    if negative["observed"] != "FIRES" or not negative["fired"]:
        return fail("negative control did not fire")

    doc = {
        "fired_on_bad": True,
        "silent_on_good": True,
        "genuine": genuine,
        "fake_token": fake,
        "fake_label": label,
        "negative_control": negative,
        "pass": True,
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "fired_on_bad=True silent_on_good=True "
        f"genuine_verdict={genuine['verdict']} fake_verdict={fake['verdict']} "
        f"label_verdict={label['verdict']} "
        f"fake_missing={fake['missing_claim_ids']}"
    )
    print(
        "negative_control rejects=token-concession-then-prepared-attack "
        f"observed=FIRES reasons={fake['reasons']}"
    )
    print("SUCCESS:CNL-0049-probe1 both-states fake-fails genuine-passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
