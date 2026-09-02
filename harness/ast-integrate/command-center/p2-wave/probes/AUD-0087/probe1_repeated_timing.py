#!/usr/bin/env python3
"""Probe 1: nine accepted uncontended timed runs; median and spread, not one sample."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import timing as T  # noqa: E402

RAW = HERE / "probe1-repeated-timing.raw.json"


def main() -> int:
    control = T.both_states_contention_control()
    collection = T.collect_samples()
    summary = T.summarize(collection)
    headline = T.headline_from_summary(summary)
    payload = {
        "probe": "probe1-repeated-timing",
        "unit_id": "AUD-0087",
        "method": "nine-accepted-fresh-prefix-wall-clock",
        "contention_control": {
            "id": control["id"],
            "pass": control["pass"],
            "fired_on_bad_state": control["fired_on_bad_state"],
            "silent_on_good_state": control["silent_on_good_state"],
            "bad_reason": control["bad_reason"],
            "good_reason": control["good_reason"],
            "detectors": control["detectors"],
        },
        "headline": headline,
        "accepted_samples": [
            {
                "label": r["label"],
                "cold_install_ms": r["cold_install_ms"],
                "first_import_process_ms": r["first_import_process_ms"],
                "first_import_statement_ms": r["first_import_statement_ms"],
                "first_command_process_ms": r["first_command_process_ms"],
                "load1": r["load_before"]["load1"],
                "nproc": r["load_before"]["nproc"],
                "procs_running": r["load_before"]["procs_running"],
                "source_match": r["source_match"],
            }
            for r in collection["accepted"]
        ],
        "discarded_samples": [
            {
                "label": r.get("label"),
                "discard_reason": r.get("discard_reason"),
                "load1": (r.get("load_before") or {}).get("load1"),
            }
            for r in collection["discarded"]
        ],
        "errors": collection["errors"],
        "pip": summary["pip"],
        "install_command": summary["install_command"],
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    if not control["pass"]:
        print("FAILED:AUD-0087-probe1 contention control does not discriminate")
        return 1
    if not collection["enough"]:
        print(
            "FAILED:AUD-0087-probe1 accepted={0} needed={1} discarded={2}".format(
                summary["accepted_samples"], T.NEEDED, summary["discarded_samples"]
            )
        )
        return 1
    if not all(r["source_match"] for r in collection["accepted"]):
        print("FAILED:AUD-0087-probe1 installed bytes do not match current source")
        return 1
    for key in (
        "cold_install_median_ms",
        "first_import_process_median_ms",
        "first_command_process_median_ms",
    ):
        val = headline.get(key)
        if not isinstance(val, (int, float)) or val <= 0:
            print(f"FAILED:AUD-0087-probe1 {key} is not a positive measurement")
            return 1
    print(
        "accepted={0} discarded={1} install_median_ms={2:.3f} "
        "import_proc_median_ms={3:.3f} command_median_ms={4:.3f}".format(
            headline["accepted_samples"],
            headline["discarded_samples"],
            headline["cold_install_median_ms"],
            headline["first_import_process_median_ms"],
            headline["first_command_process_median_ms"],
        )
    )
    print("SUCCESS:AUD-0087-probe1 nine-sample uncontended timing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
