#!/usr/bin/env python3
"""Probe 1: test_unknown_field_rejected_per_parser.

Each production parser must hard-reject an extra unknown field and the
error text must name that field. The json.loads control must ACCEPT so
the detector is live (both-states).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import kinds  # noqa: E402

UNIT = "TST-0052"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    report = kinds.measure_all()
    print(json.dumps(
        {
            "unit_id": UNIT,
            "probe": "test_unknown_field_rejected_per_parser",
            "unknown_field": report["unknown_field"],
            "production_count": report["production_count"],
            "production_unknown_all_rejected": report["production_unknown_all_rejected"],
            "production_errors_all_name_field": report["production_errors_all_name_field"],
            "lenient_control_accepts_unknown": report["lenient_control_accepts_unknown"],
            "silently_accepting_production_parsers": report[
                "silently_accepting_production_parsers"
            ],
            "rows": [
                {
                    "kind": r["kind"],
                    "production": r["production"],
                    "unknown_rejected": r["unknown_rejected"],
                    "error_names_field": r["error_names_field"],
                    "unknown_error": r["unknown_error"],
                }
                for r in report["rows"]
            ],
        },
        sort_keys=True,
    ))
    if report["production_count"] < 4:
        return fail(f"need >=4 production parsers, got {report['production_count']}")
    if not report["production_unknown_all_rejected"]:
        return fail(
            "production parser accepted unknown field: "
            + ",".join(report["silently_accepting_production_parsers"])
        )
    if not report["production_errors_all_name_field"]:
        silent = [
            r["kind"]
            for r in report["rows"]
            if r["production"] and not r["error_names_field"]
        ]
        return fail(f"rejection did not name the field: {silent}")
    if not report["lenient_control_accepts_unknown"]:
        return fail("lenient json.loads control did not accept unknown field (detector inert)")
    if not report["lenient_control_retains_value"]:
        return fail("lenient control did not retain the ignored value on the dict")
    print(f"SUCCESS:{UNIT}-probe1 unknown-field-rejected-per-parser")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
