#!/usr/bin/env python3
"""Probe 2: every domain type has a generator or is listed as ungenerated.

Catalog test: test_every_domain_type_has_a_generator_or_is_listed_as_ungenerated.

Independent of probe1's shrink path: live schema-file census + field-space
coverage of the four named generators. Does not rewrite the catalog receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

UNIT = "TST-0116"


def main() -> int:
    report = H.generator_inventory_check()
    slim = {
        "probe": "probe2-generator-inventory",
        "unit_id": UNIT,
        "pass": report.get("pass"),
        "checks": report.get("checks"),
        "generated_ids": report.get("generated_ids"),
        "ungenerated_count": report.get("ungenerated_count"),
        "ungenerated_ids": report.get("ungenerated_ids"),
        "schema_examples": report.get("schema_examples"),
        "coverage": report.get("coverage"),
        "answer": report.get("answer"),
    }
    print(json.dumps(slim, sort_keys=True))
    if not report.get("pass"):
        print("FAILED:TST-0116-probe2 generator inventory")
        print(json.dumps(report.get("checks"), indent=2)[:3000])
        return 1
    print(
        f"generated={report.get('generated_ids')} "
        f"ungenerated_count={report.get('ungenerated_count')} "
        "coverage_ok=True schema_examples_valid=True"
    )
    print(f"SUCCESS:{UNIT}-probe2 every domain type generated or listed ungenerated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
