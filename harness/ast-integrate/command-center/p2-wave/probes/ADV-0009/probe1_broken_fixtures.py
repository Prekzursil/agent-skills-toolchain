#!/usr/bin/env python3
"""Probe 1: known-BROKEN (and paired known-good) via in-process library calls.

Records whether each detector emits a flagging result on the broken fixture.
Does not invoke production CLIs (probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit as A  # noqa: E402

OUT = HERE / "probe1-broken.raw.json"


def main() -> int:
    report = A.run_instrument("library")
    slim = {
        "probe": "probe1-broken-library",
        "unit_id": "ADV-0009",
        "instrument": "library",
        "pass": report["pass"],
        "errors": report["errors"],
        "n_valid": report["n_valid"],
        "n_silent_in_both": report["n_silent_in_both"],
        "n_fired_on_broken": report["n_fired_on_broken"],
        "valid_ids": report["valid_ids"],
        "silent_in_both_ids": report["silent_in_both_ids"],
        "fired_on_broken_ids": report["fired_on_broken_ids"],
        "meta_control": {
            "detector_id": report["meta_control"]["detector_id"],
            "reason": report["meta_control"]["reason"],
            "valid": report["meta_control"]["valid"],
            "fired_on_bad_state": report["meta_control"]["fired_on_bad_state"],
            "silent_on_good_state": report["meta_control"]["silent_on_good_state"],
        },
        "calibration": report["calibration"],
        "claimed_validate_checks": report["claimed_validate_checks"],
        "executed_validate_checks": report["executed_validate_checks"],
        "unexecuted_validate_checks": report["unexecuted_validate_checks"],
        "rows": [
            {
                "detector_id": r["detector_id"],
                "reason": r["reason"],
                "valid": r["valid"],
                "fired_on_bad_state": r["fired_on_bad_state"],
                "silent_on_good_state": r["silent_on_good_state"],
                "status": A.status_for(r),
            }
            for r in report["rows"]
        ],
        "substrate_absent": [r["id"] for r in report["substrate"]["absent"]],
    }
    OUT.write_text(json.dumps(slim, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(slim, sort_keys=True))
    print(
        f"valid={slim['n_valid']} silent_both={slim['n_silent_in_both']} "
        f"fired_broken={slim['n_fired_on_broken']} "
        f"vfields_bare={slim['meta_control']['reason']}"
    )
    if not report["pass"]:
        print("FAILED:ADV-0009-probe1 " + "; ".join(report["errors"][:6]))
        return 1
    print("SUCCESS:ADV-0009-probe1 library known-broken/known-good both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
