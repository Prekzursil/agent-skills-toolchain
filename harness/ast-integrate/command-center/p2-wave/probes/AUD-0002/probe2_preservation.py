#!/usr/bin/env python3
"""Probe 2: sha256 preservation search, not path-name match.

Catalog control: seed a file that exists ONLY in one worktree and confirm
UNPRESERVED; copy the same bytes onto main at a different path and confirm
the prober flips to PRESERVED.
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

ART = REPO / "command-center/audit/AUD-0002-worktree-inventory.json"
SCHEMA = REPO / "command-center/schema/audit-inventory.schema.json"
RAW = HERE / "probe2-preservation.raw.json"
SENTINEL = (
    "SUCCESS:AUD-0002 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0002-probe2 {msg}")
    return 1


def main() -> int:
    control = I.run_preservation_control()
    payload = {**control, "pass": False, "garbage_rejected": 0}

    if not control["unpreserved_before_copy"]:
        I.dump_json(RAW, payload)
        return fail(f"seed not UNPRESERVED before copy before={control['before']}")
    if not control["preserved_after_copy"]:
        I.dump_json(RAW, payload)
        return fail(f"seed not PRESERVED after copy after={control['after']}")
    if not control["flipped"]:
        I.dump_json(RAW, payload)
        return fail("control did not flip UNPRESERVED -> PRESERVED")
    if not control["path_name_match_rejected"]:
        I.dump_json(RAW, payload)
        return fail("path-name strawman not rejected (same path, different bytes)")
    if control["copy_relpath"] == I.SEED_REL:
        I.dump_json(RAW, payload)
        return fail("copy used the same relative path; would not prove content search")

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

    payload["pass"] = True
    I.dump_json(RAW, payload)
    print(
        json.dumps(
            {
                "before": control["before"],
                "after": control["after"],
                "flipped": control["flipped"],
                "path_name_match_rejected": control["path_name_match_rejected"],
                "seed_sha256": control["seed_sha256"],
                "copy_relpath": control["copy_relpath"],
                "garbage_rejected": payload["garbage_rejected"],
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:AUD-0002-probe2 sha256 preservation flips after copy; "
        "path-name match is not proof"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
