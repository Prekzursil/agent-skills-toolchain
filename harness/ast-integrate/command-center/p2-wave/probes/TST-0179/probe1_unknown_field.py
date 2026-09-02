#!/usr/bin/env python3
"""Probe 1: both-states unknown-field rejection with the field named.

Good state: a clean manifest is accepted by the strict parser.
Bad state:  the same document plus one unknown top-level field is rejected,
            and the error names that field.
Mutation:   the unmodified vendor schema (no overlay) accepts the dirty
            document, proving the overlay is the rule under test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from emitter import CLEAN_MANIFEST, PLANTED_UNKNOWN_FIELD, emit_plugin_manifest
from strict_parser import parse_manifest


def run() -> dict:
    clean = emit_plugin_manifest(CLEAN_MANIFEST)
    dirty = dict(clean)
    dirty[PLANTED_UNKNOWN_FIELD] = True

    good = parse_manifest(clean, strict=True)
    bad = parse_manifest(dirty, strict=True)
    lenient_dirty = parse_manifest(dirty, strict=False)
    missing = parse_manifest({"version": "1.0.0"}, strict=True)

    named = bad["named_unknown_fields_from_parser"]
    named_diff = bad["named_unknown_fields_from_diff"]
    error_text = " | ".join(bad["error_messages"])
    names_field = PLANTED_UNKNOWN_FIELD in named and PLANTED_UNKNOWN_FIELD in error_text

    ok = (
        good["accepted"] is True
        and bad["accepted"] is False
        and names_field
        and named == named_diff == [PLANTED_UNKNOWN_FIELD]
        and bad["error_names_field"] is True
        and lenient_dirty["accepted"] is True
        and missing["accepted"] is False
        and any("name" in m for m in missing["error_messages"])
    )
    return {
        "probe": "probe1-unknown-field",
        "unit_id": "TST-0179",
        "pass": ok,
        "clean_accepted": good["accepted"],
        "dirty_rejected": not bad["accepted"],
        "dirty_error_names_field": names_field,
        "parser_named_fields": named,
        "diff_named_fields": named_diff,
        "dirty_error_messages": bad["error_messages"],
        "lenient_accepts_unknown": lenient_dirty["accepted"],
        "missing_name_rejected": not missing["accepted"],
        "planted_field": PLANTED_UNKNOWN_FIELD,
        "clean_keys": sorted(clean.keys()),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, sort_keys=True))
    if result["pass"]:
        print(
            "SUCCESS:TST-0179-probe1 clean accepted; unknown field "
            f"{result['planted_field']!r} rejected and named; lenient control fired"
        )
        return 0
    print("FAILED:TST-0179-probe1 both-states unknown-field control")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
