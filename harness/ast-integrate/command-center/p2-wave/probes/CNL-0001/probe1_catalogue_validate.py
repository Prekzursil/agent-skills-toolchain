#!/usr/bin/env python3
"""Probe 1: Draft202012Validator over all 130 catalogue records against the live envelope.

Independent of probe 2 (this probe does not do set-algebra or round-trip). Requires
0 errors on every reconstructed protocol/preset, plus a deliberately invalid record
proving the validator is not vacuous.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from envelope import ARTIFACT_REL, SENTINEL  # noqa: E402
from fixtures import catalogue_records, cm01  # noqa: E402


def err_count(validator: Draft202012Validator, instance: object) -> int:
    return sum(1 for _ in validator.iter_errors(instance))


def main() -> int:
    art = REPO / ARTIFACT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        print("FAILED:CNL-0001-probe1 envelope artifact missing")
        return 1
    text = art.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNL-0001-probe1 sentinel-absent")
        return 1
    schema = json.loads(text)
    if schema.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0001-probe1 self-declared", schema.get("state"))
        return 1
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    records = catalogue_records()
    if len(records) != 130:
        print(f"FAILED:CNL-0001-probe1 record_count={len(records)} want=130")
        return 1
    protocols = [r for r in records if str(r.get("id", "")).startswith("P")]
    presets = [r for r in records if not str(r.get("id", "")).startswith("P")]
    if len(protocols) != 58 or len(presets) != 72:
        print(
            f"FAILED:CNL-0001-probe1 split protocols={len(protocols)} presets={len(presets)}"
        )
        return 1

    failures = []
    for rec in records:
        n = err_count(validator, rec)
        if n:
            failures.append({"id": rec.get("id"), "errors": n})
    if failures:
        print(json.dumps({"pass": False, "failures": failures[:8]}, indent=2))
        print(f"FAILED:CNL-0001-probe1 errors_on={len(failures)}")
        return 1

    bad = deepcopy(cm01())
    bad["not_a_section"] = "planted-additional-property"
    bad_n = err_count(validator, bad)
    if bad_n < 1:
        print("FAILED:CNL-0001-probe1 invalid record produced 0 errors (vacuous)")
        return 1

    empty_n = err_count(validator, {})
    garbage_n = err_count(validator, {"totally": "unrelated", "passing_tests": 999999})
    if empty_n < 1 or garbage_n < 1:
        print("FAILED:CNL-0001-probe1 garbage accepted (vacuous envelope)")
        return 1

    out = {
        "probe": "probe1-catalogue-validate",
        "unit_id": "CNL-0001",
        "validator": "jsonschema.Draft202012Validator",
        "records": 130,
        "protocols": 58,
        "presets": 72,
        "error_count_sum": 0,
        "invalid_record_id": "C-M01+not_a_section",
        "invalid_record_errors": bad_n,
        "empty_object_errors": empty_n,
        "garbage_errors": garbage_n,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"validated=130 errors=0 invalid_errors={bad_n} "
        f"empty_errors={empty_n} garbage_errors={garbage_n}"
    )
    print("SUCCESS:CNL-0001-probe1 catalogue records validate; invalid control fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
