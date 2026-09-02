#!/usr/bin/env python3
"""Probe 2: pin assertion.

The validator version is recorded in the conformance report (when present) and
a version mismatch fails the gate. Both states: matching pin is silent,
mismatched pin raises PinMismatch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import schema_resolver as SR  # noqa: E402

OUT = HERE / "probe2-pin.raw.json"
REPORT = REPO / "command-center/phase4/conformance/ARC-0102.json"
PIN_PATH = HERE / "pin.json"


def _write_pin(pinned_version: str) -> None:
    original = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    mutated = dict(original)
    mutated["pinned_version"] = pinned_version
    PIN_PATH.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    original_bytes = PIN_PATH.read_bytes()
    original = json.loads(original_bytes.decode("utf-8"))
    observed = SR.observed_jsonschema_version()
    match_error = None
    mismatch_error = None
    match_silent = False
    mismatch_fired = False
    try:
        match_record = SR.assert_pin()
        match_silent = True
    except SR.PinMismatch as exc:
        match_error = str(exc)
        match_record = None

    restored = False
    try:
        _write_pin("0.0.0-not-the-pin")
        try:
            SR.assert_pin()
        except SR.PinMismatch as exc:
            mismatch_fired = True
            mismatch_error = str(exc)
    finally:
        PIN_PATH.write_bytes(original_bytes)
        restored = PIN_PATH.read_bytes() == original_bytes

    after = SR.assert_pin()
    report_records_version = None
    report_match = None
    if REPORT.is_file():
        doc = json.loads(REPORT.read_text(encoding="utf-8"))
        pin_block = doc.get("validator_pin") if isinstance(doc, dict) else None
        if isinstance(pin_block, dict):
            report_records_version = pin_block.get("pinned_version")
            report_match = (
                pin_block.get("pinned_version") == original.get("pinned_version")
                and pin_block.get("observed_version") == observed
            )

    payload = {
        "observed_version": observed,
        "pinned_version": original.get("pinned_version"),
        "match_silent": match_silent,
        "match_record": match_record,
        "match_error": match_error,
        "mismatch_fired": mismatch_fired,
        "mismatch_error": mismatch_error,
        "pin_restored": restored,
        "after_restore": after,
        "report_present": REPORT.is_file(),
        "report_records_version": report_records_version,
        "report_match": report_match,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if not match_silent:
        print("FAILED:ARC-0102-probe2 matching pin was not silent", match_error)
        return 1
    if not mismatch_fired:
        print("FAILED:ARC-0102-probe2 mismatch did not fail the gate")
        return 1
    if "0.0.0-not-the-pin" not in (mismatch_error or ""):
        print("FAILED:ARC-0102-probe2 mismatch error did not name the bad pin")
        return 1
    if not restored:
        print("FAILED:ARC-0102-probe2 pin.json not restored")
        return 1
    if REPORT.is_file() and report_match is not True:
        print("FAILED:ARC-0102-probe2 report does not record matching pin")
        return 1

    print(
        "pinned="
        + str(original.get("pinned_version"))
        + " observed="
        + observed
        + " match_silent="
        + str(match_silent)
        + " mismatch_fired="
        + str(mismatch_fired)
        + " report_records_version="
        + str(report_records_version)
    )
    print("SUCCESS:ARC-0102-probe2 pin gate both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
