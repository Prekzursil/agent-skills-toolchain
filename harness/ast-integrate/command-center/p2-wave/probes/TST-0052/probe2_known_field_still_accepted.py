#!/usr/bin/env python3
"""Probe 2: test_known_field_still_accepted (both-states pair).

The same production parsers that reject an unknown field must still
accept the unmodified known-good document. Independent of probe 1's
summary: this process re-runs the live loaders.
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
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    report = kinds.measure_all()
    production = [r for r in report["rows"] if r["production"]]
    print(json.dumps(
        {
            "unit_id": UNIT,
            "probe": "test_known_field_still_accepted",
            "production_known_all_accepted": report["production_known_all_accepted"],
            "production_unknown_all_rejected": report["production_unknown_all_rejected"],
            "rows": [
                {
                    "kind": r["kind"],
                    "known_accepted": r["known_accepted"],
                    "known_error": r["known_error"],
                    "unknown_rejected": r["unknown_rejected"],
                    "known_keys": r["known_keys"],
                }
                for r in production
            ],
        },
        sort_keys=True,
    ))
    if not production:
        return fail("no production parsers measured")
    bad_known = [r["kind"] for r in production if not r["known_accepted"]]
    if bad_known:
        details = {r["kind"]: r["known_error"] for r in production if not r["known_accepted"]}
        return fail(f"known-good rejected: {details}")
    still_unknown = [r["kind"] for r in production if not r["unknown_rejected"]]
    if still_unknown:
        return fail(
            "both-states broken: known-good accepted but unknown field not rejected: "
            + ",".join(still_unknown)
        )
    if not report["lenient_control_accepts_unknown"]:
        return fail("lenient control no longer discriminates (accepts unknown)")
    print(f"SUCCESS:{UNIT}-probe2 known-field-still-accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
