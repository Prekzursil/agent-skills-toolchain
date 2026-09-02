#!/usr/bin/env python3
"""Probe 2: lock reconciliation plus the out-of-range pin control.

A manifest-only read cannot detect a lock pin outside the declared range.
This probe diffs declared constraints against uv.lock / poetry.lock /
Pipfile.lock, and injects an out-of-range pin into a fixture lock to
prove the differ fires on the bad state and stays silent on the good one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

ART = REPO / "command-center/audit/AUD-0020-python-dep-inventory.json"
SCHEMA = REPO / "command-center/schema/audit-inventory.schema.json"
RAW = HERE / "probe2-lock-reconciliation.json"
CTL = HERE / "control-out-of-range-pin.json"
SENTINEL = (
    "SUCCESS:AUD-0020 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0020-probe2 {msg}")
    return 1


def main() -> int:
    ctl = I.pin_control()
    I.dump_json(CTL, ctl)
    packages = I.scan_packages()
    head = I.headline(packages)
    preserve = I.run_preservation_control()
    payload = {
        "ok": False,
        "packages_with_parsed_lock": head["packages_with_parsed_lock"],
        "packages_without_parsed_lock": head["packages_without_parsed_lock"],
        "out_of_range_pins": head["out_of_range_pins"],
        "declared_missing_from_lock": head["declared_missing_from_lock"],
        "undecidable_constraints": head["undecidable_constraints"],
        "uv_lock_files": head["uv_lock_files"],
        "poetry_lock_files": head["poetry_lock_files"],
        "pipfile_lock_files": head["pipfile_lock_files"],
        "violations": head["violations"],
        "missing_from_lock": head["missing_from_lock"],
        "undecidable": head["undecidable"],
        "pin_control": {
            "fires_on_out_of_range": ctl["fires_on_out_of_range"],
            "silent_on_in_range": ctl["silent_on_in_range"],
            "ok": ctl["ok"],
        },
        "preservation_control": {
            "unpreserved_before_copy": preserve["unpreserved_before_copy"],
            "preserved_after_copy": preserve["preserved_after_copy"],
            "path_name_match_rejected": preserve["path_name_match_rejected"],
            "flipped": preserve["flipped"],
        },
        "garbage_rejected": 0,
    }
    if not ctl["ok"]:
        I.dump_json(RAW, payload)
        return fail("out-of-range pin control did not discriminate")
    if not (
        preserve["unpreserved_before_copy"]
        and preserve["preserved_after_copy"]
        and preserve["flipped"]
        and preserve["path_name_match_rejected"]
    ):
        I.dump_json(RAW, payload)
        return fail(f"preservation control {preserve}")

    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        if SENTINEL not in text:
            I.dump_json(RAW, payload)
            return fail("artifact missing completion sentinel")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            I.dump_json(RAW, payload)
            return fail(f"self-declared {doc.get('state')}")
        rec = doc.get("preservation_control") or {}
        if rec.get("unpreserved_before_copy") is not True:
            I.dump_json(RAW, payload)
            return fail("artifact did not record unpreserved_before_copy")
        if rec.get("preserved_after_copy") is not True:
            I.dump_json(RAW, payload)
            return fail("artifact did not record preserved_after_copy")
        if rec.get("flipped") is not True:
            I.dump_json(RAW, payload)
            return fail("artifact did not record flipped")
        if rec.get("path_name_match_rejected") is not True:
            I.dump_json(RAW, payload)
            return fail("artifact did not record path_name_match_rejected")
        pin = doc.get("pin_control") or {}
        if pin.get("fires_on_out_of_range") is not True:
            I.dump_json(RAW, payload)
            return fail("artifact did not record pin control fire")
        if pin.get("silent_on_in_range") is not True:
            I.dump_json(RAW, payload)
            return fail("artifact did not record pin control silence")
        if not SCHEMA.is_file():
            I.dump_json(RAW, payload)
            return fail("schema missing")
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        if errors:
            I.dump_json(RAW, payload)
            return fail(f"schema {errors[0].message}")
        rejected = 0
        for garbage in GARBAGE:
            if list(validator.iter_errors(garbage)):
                rejected += 1
        payload["garbage_rejected"] = rejected
        if rejected != 3:
            I.dump_json(RAW, payload)
            return fail(f"schema garbage rejected {rejected}/3")

    payload["ok"] = True
    I.dump_json(RAW, payload)
    print(
        json.dumps(
            {
                "packages_with_parsed_lock": head["packages_with_parsed_lock"],
                "packages_without_parsed_lock": head["packages_without_parsed_lock"],
                "out_of_range_pins": head["out_of_range_pins"],
                "declared_missing_from_lock": head["declared_missing_from_lock"],
                "undecidable_constraints": head["undecidable_constraints"],
                "pin_control_ok": ctl["ok"],
                "preservation_flipped": preserve["flipped"],
                "garbage_rejected": payload["garbage_rejected"],
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:AUD-0020-probe2 lock reconciliation ran; out-of-range pin "
        "control discriminated; preservation control flipped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
