#!/usr/bin/env python3
"""Probe 2: known-GOOD (and paired known-broken) via production CLIs.

Mechanically different from probe 1: validate.py / shard_reducer.py /
bundle_secret_scan.py argv and subprocess python -c wrappers, not
in-process validate(). Independently re-classifies the V-FIELDS-bare
meta-control. If this probe would mark that detector VALID, the audit
itself is broken.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit as A  # noqa: E402

OUT = HERE / "probe2-good.raw.json"


def main() -> int:
    report = A.run_instrument("cli")
    meta = report["meta_control"]
    would_pass_disarmed = bool(meta.get("valid"))
    slim = {
        "probe": "probe2-good-cli",
        "unit_id": "ADV-0009",
        "instrument": "cli",
        "pass": report["pass"] and not would_pass_disarmed,
        "errors": list(report["errors"]),
        "n_valid": report["n_valid"],
        "n_silent_in_both": report["n_silent_in_both"],
        "n_fired_on_broken": report["n_fired_on_broken"],
        "valid_ids": report["valid_ids"],
        "silent_in_both_ids": report["silent_in_both_ids"],
        "fired_on_broken_ids": report["fired_on_broken_ids"],
        "meta_control": {
            "detector_id": meta["detector_id"],
            "reason": meta["reason"],
            "valid": meta["valid"],
            "fired_on_bad_state": meta["fired_on_bad_state"],
            "silent_on_good_state": meta["silent_on_good_state"],
            "would_pass_disarmed_as_valid": would_pass_disarmed,
        },
        "independent_of_probe1_library": True,
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
    if would_pass_disarmed:
        slim["errors"] = slim["errors"] + [
            "CLI instrument classified known-disarmed V-FIELDS-bare as VALID"
        ]
        slim["pass"] = False
    OUT.write_text(json.dumps(slim, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(slim, sort_keys=True))
    print(
        f"valid={slim['n_valid']} silent_both={slim['n_silent_in_both']} "
        f"fired_broken={slim['n_fired_on_broken']} "
        f"vfields_bare={slim['meta_control']['reason']} "
        f"would_pass_disarmed={would_pass_disarmed}"
    )
    if not slim["pass"]:
        print("FAILED:ADV-0009-probe2 " + "; ".join(slim["errors"][:6]))
        return 1
    print(
        "SUCCESS:ADV-0009-probe2 CLI known-good/known-broken; "
        "V-FIELDS-bare classified silent-in-both"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
