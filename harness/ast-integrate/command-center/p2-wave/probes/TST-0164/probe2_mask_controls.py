#!/usr/bin/env python3
"""Probe 2: independent reviewer — undeclared ND field + mask-coverage ceiling.

Does not import probe1. Rebuilds measurements and AST-checks that the mask
list is a literal declared up front.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from mask import (  # noqa: E402
    DECLARED_NONDETERMINISTIC_FIELDS,
    MaskCoverageError,
    check_mask_coverage,
    declared_fields_are_literals,
    mask_module_imports_diff_walker,
)
from measure import collect  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0164.json"
SCHEMA = HERE / "resume_report.schema.json"
SENTINEL = "SUCCESS:TST-0164"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0164-probe2 {msg}")
    return 1


def main() -> int:
    data = collect()
    flags = data["flags"]
    cov = data["mask_coverage"]
    undecl = data["undeclared_nd"]
    print(
        json.dumps(
            {
                "declared_fields_are_literals": flags["declared_fields_are_literals"],
                "mask_not_imported_from_diff": flags["mask_not_imported_from_diff"],
                "undeclared_normalized_identical": undecl["normalized_diff"]["identical"],
                "undeclared_first_file": undecl["normalized_diff"]["first_file"],
                "blanket_rejected": cov["blanket"]["rejected"],
                "blanket_reason": cov["blanket"].get("reason"),
                "mask_everything_rejected": cov["mask_everything"]["rejected"],
                "mask_everything_reason": cov["mask_everything"].get("reason"),
                "semantic_rejected": cov["semantic_field"]["rejected"],
                "session_nonce_in_declared_mask": "session_nonce"
                in data["declared_nondeterministic_fields"],
            },
            indent=2,
            sort_keys=True,
        )
    )

    if not declared_fields_are_literals():
        return fail("DECLARED_NONDETERMINISTIC_FIELDS is not a tuple of string literals")
    if mask_module_imports_diff_walker():
        return fail("mask.py imports a diff walker (mask would be discovered, not declared)")
    if "session_nonce" in DECLARED_NONDETERMINISTIC_FIELDS:
        return fail("session_nonce is in the declared mask; undeclared control is dead")
    if not flags["undeclared_nd_fails_normalized"]:
        return fail("undeclared session_nonce was absorbed by the mask (blanket)")
    if undecl["normalized_diff"]["identical"] is True:
        return fail("defective run normalized-identical; mask is not discriminating")
    if not flags["undeclared_nd_semantic_still_equal"]:
        return fail("session_nonce plant also moved semantic payload (control is mixed)")
    if not flags["blanket_mask_rejected"]:
        return fail("blanket token '*' was not rejected")
    if cov["blanket"].get("reason") != "mask-coverage-ceiling":
        return fail(f"blanket reason {cov['blanket'].get('reason')!r} != mask-coverage-ceiling")
    if not flags["mask_everything_rejected"]:
        return fail("masking every leaf was not rejected")
    if not flags["semantic_mask_rejected"]:
        return fail("masking downstream.transform_digest was not rejected")
    try:
        check_mask_coverage(["payload.sha256"])
        return fail("payload.sha256 was accepted as a mask field")
    except MaskCoverageError as exc:
        if exc.reason != "unmaskable-semantic-field":
            return fail(f"payload.sha256 reason {exc.reason!r}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    garbage = {"totally": "unrelated", "passing_tests": 999999, "state": "SUCCESS"}
    g_errs = list(jsonschema.Draft7Validator(schema).iter_errors(garbage))
    print(f"garbage_schema_errors={len(g_errs)}")
    if not g_errs:
        return fail("resume_report schema accepted unrelated garbage")

    if not RECEIPT.is_file():
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("receipt sentinel absent")
    r_errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if r_errs:
        return fail(f"receipt schema {r_errs[0].message}")
    if doc.get("both_states", {}).get("undeclared_field_fails_normalized") is not True:
        return fail("receipt both_states.undeclared_field_fails_normalized is not true")
    if doc.get("mask_coverage_ceiling", {}).get("blanket_rejected") is not True:
        return fail("receipt did not record blanket rejection")
    if doc.get("mask_discovered_by_diffing") is not False:
        return fail("receipt mask_discovered_by_diffing is not false")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"receipt self-declared {doc.get('state')}")
    print("SUCCESS:TST-0164-probe2 undeclared-ND + mask-coverage ceiling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
