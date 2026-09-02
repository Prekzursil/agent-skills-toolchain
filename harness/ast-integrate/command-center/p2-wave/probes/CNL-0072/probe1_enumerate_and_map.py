#!/usr/bin/env python3
"""Probe 1: enumerate 17 + 6 independently, total mapping, jsonschema both-states.

Planted-bad = a preset whose outcome is 'PASS' (not in the 17) -> validator FIRES.
Known-good = 72 records covering only the 17 -> validator SILENT (0 errors).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import taxonomy as T  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0072-outcome-taxonomy-6-spec-variants-against-the-17-value-enum.md"
)
INVALID = {
    "id": "C-99",
    "artifact_type": "council-preset",
    "outcome": "PASS",
}


def fmt_errors(errs: list) -> str:
    return "; ".join(e.message for e in errs[:4]) or "none"


def main() -> int:
    enum_info = T.outcome_enum()
    enum_ids = enum_info["ids"]
    variants = T.spec_variants_from_catalog()
    variant_ids = [v["id"] for v in variants]
    table = T.mapping_table(enum_ids, variant_ids)
    schema = T.outcome_schema(enum_ids)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    recs = T.presets72(enum_ids)
    good_errors = 0
    for rec in recs:
        good_errors += len(list(validator.iter_errors(rec)))
    bad_errs = list(validator.iter_errors(INVALID))
    usage = T.library_usage(enum_ids)
    var_outside = T.variants_used_outside_enum(variant_ids, set(enum_ids))
    unmapped = [r for r in table if r["kind"] == "unmapped" or r["variant"] is None]
    mapped = [r for r in table if r["variant"] is not None]
    identity = [r for r in table if r["kind"] == "identity"]
    special = [r for r in table if r["kind"] == "specialization"]

    print(f"ENUM source={enum_info['source']} n={len(enum_ids)} path={enum_info['path']}")
    print("ENUM ids=" + ",".join(enum_ids))
    print("VARIANTS n=6 ids=" + ",".join(variant_ids))
    print(
        f"MAPPING n={len(table)} mapped={len(mapped)} unmapped={len(unmapped)} "
        f"identity={len(identity)} specialization={len(special)}"
    )
    print(
        f"USAGE source={usage['source']} n_records={usage['n_records']} "
        f"outside_count={usage['outside_count']} outside={usage['outside']}"
    )
    print(f"VARIANT_IDS_OUTSIDE_ENUM={var_outside}")
    print(f"KNOWN-GOOD 72-record schema_error_count={good_errors}")
    print(
        f"PLANTED-BAD outcome=PASS schema_error_count={len(bad_errs)} "
        f"errors={fmt_errors(bad_errs)}"
    )

    if len(enum_ids) != 17 or len(set(enum_ids)) != 17:
        print("FAILED:CNL-0072-probe1 enum is not 17 unique values")
        return 1
    if len(variant_ids) != 6:
        print("FAILED:CNL-0072-probe1 variants is not 6")
        return 1
    if len(table) != 17:
        print("FAILED:CNL-0072-probe1 mapping table is not total over 17")
        return 1
    if unmapped:
        print(f"FAILED:CNL-0072-probe1 unmapped enum values: {unmapped}")
        return 1
    if len(identity) != 6:
        print(f"FAILED:CNL-0072-probe1 expected 6 identity rows, got {len(identity)}")
        return 1
    if sorted(r["enum"] for r in identity) != sorted(variant_ids):
        print("FAILED:CNL-0072-probe1 identity rows are not exactly the 6 variants")
        return 1
    targets = {r["variant"] for r in mapped}
    if targets != set(variant_ids):
        print(f"FAILED:CNL-0072-probe1 mapping does not hit every variant: {targets}")
        return 1
    if var_outside:
        print("FAILED:CNL-0072-probe1 a spec variant has no home in the 17-enum")
        return 1
    if usage["outside_count"] != 0:
        print("FAILED:CNL-0072-probe1 values used outside the enum")
        return 1
    if good_errors != 0:
        print("FAILED:CNL-0072-probe1 known-good schema errors not 0")
        return 1
    if len(bad_errs) < 1:
        print("FAILED:CNL-0072-probe1 planted-bad did not FIRE (vacuous validator)")
        return 1
    if not any("PASS" in (e.message or "") or "enum" in (e.message or "").lower() for e in bad_errs):
        # Still a fire; accept any validation error on the invalid record.
        pass

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec_enum = doc.get("enum_17") or {}
        rec_ids = rec_enum.get("ids") or []
        if rec_ids != enum_ids:
            print("FAILED:CNL-0072-probe1 artifact enum drift")
            return 1
        rec_map = doc.get("mapping_table") or []
        live_pairs = [(r["enum"], r["variant"]) for r in table]
        art_pairs = [(r.get("enum"), r.get("variant")) for r in rec_map]
        if live_pairs != art_pairs:
            print("FAILED:CNL-0072-probe1 artifact mapping drift")
            return 1
        if int(doc.get("schema_validation", {}).get("good_error_count", -1)) != 0:
            print("FAILED:CNL-0072-probe1 artifact good_error_count drift")
            return 1
        if int(doc.get("schema_validation", {}).get("invalid_error_count", 0)) < 1:
            print("FAILED:CNL-0072-probe1 artifact invalid_error_count drift")
            return 1

    print(
        "NEGATIVE CONTROL verbatim: on outcome='PASS' (not in the 17-enum) "
        f"Draft202012Validator error_count={len(bad_errs)} and FIRES; "
        f"on the 72-record known-good covering only the 17, error_count=0 and is SILENT."
    )
    print(
        "BOTH-STATES: FIRED on planted-bad PASS; SILENT on known-good 72; "
        f"outside_enum_either_direction=0 (usage_outside={usage['outside_count']} "
        f"variant_outside={len(var_outside)})"
    )
    print("SUCCESS:CNL-0072-probe1 enumerate-map jsonschema both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
