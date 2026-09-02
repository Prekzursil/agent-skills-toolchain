#!/usr/bin/env python3
"""Named probe 1: numeric-range census + planted unbounded-integer detector.

Walks live artifact schemas, reports which integer/number fields can exceed
2^53, and names JS consumers under tools/lib/*.mjs. A planted unbounded
byte_count MUST be found; a planted max=255 exit_code MUST NOT be.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import (  # noqa: E402
    MAX_SAFE,
    REPO,
    detector_on_schema_file,
    live_census,
)

PLANTED_BAD = HERE / "fixtures" / "planted-unbounded.schema.json"
PLANTED_GOOD = HERE / "fixtures" / "planted-bounded.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0056-probe1 {msg}")
    return 1


def main() -> int:
    if not PLANTED_BAD.is_file() or not PLANTED_GOOD.is_file():
        return fail("planted schema fixtures missing")

    planted_hits = detector_on_schema_file(PLANTED_BAD, REPO)
    if not planted_hits:
        return fail("detector missed planted unbounded byte_count")
    if not any(h.get("name") == "byte_count" and h.get("can_exceed_2_53") for h in planted_hits):
        return fail(f"planted hits did not name byte_count: {planted_hits}")

    good_hits = detector_on_schema_file(PLANTED_GOOD, REPO)
    if good_hits:
        return fail(f"bounded exit_code flagged as exceeding 2^53: {good_hits}")

    report = live_census(REPO)
    if report["schema_file_count"] < 1:
        return fail("no artifact schemas found")
    if report["parse_failures"]:
        return fail(f"schema parse failures {report['parse_failures']}")
    if report["numeric_field_count"] < 1:
        return fail("census found zero numeric fields")

    js = report["js_consumers"]
    ledger = [r for r in js if r["path"].endswith("handled-ledger.mjs")]
    if not ledger:
        return fail("tools/lib/handled-ledger.mjs not in JS consumer census")
    if not ledger[0].get("has_lossless"):
        return fail("handled-ledger.mjs has no parseLossless rewrite")

    js_unbounded = report.get("js_consumed_unbounded_integers") or []
    if js_unbounded:
        return fail(
            "JS-consumed schema still unbounded: " + json.dumps(js_unbounded)
        )

    widest = report.get("widest") or {}
    payload = {
        "pass": True,
        "probe": "probe1-field-census",
        "unit_id": "TST-0056",
        "max_safe_integer": MAX_SAFE,
        "schema_file_count": report["schema_file_count"],
        "numeric_field_count": report["numeric_field_count"],
        "can_exceed_2_53_count": report["can_exceed_2_53_count"],
        "wide_named_exceeding_count": report["wide_named_exceeding_count"],
        "widest": widest,
        "exceeding_sample": report["exceeding"][:12],
        "js_consumers": js,
        "js_consumed_schema": report["js_consumed_schema"],
        "js_consumed_numeric_fields": report["js_consumed_numeric_fields"],
        "planted_unbounded_found": True,
        "planted_bounded_silent": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"schemas={report['schema_file_count']} numeric={report['numeric_field_count']} "
        f"exceed={report['can_exceed_2_53_count']} widest={widest.get('schema')}"
        f"{widest.get('pointer')}"
    )
    print("SUCCESS:TST-0056-probe1 field census; planted unbounded found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
