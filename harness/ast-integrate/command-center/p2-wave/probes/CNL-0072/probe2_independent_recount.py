#!/usr/bin/env python3
"""Probe 2: independent recount. Does not import taxonomy.mapping_table.

Mechanisms (different from probe 1):
  * 17-enum from walking v1_outcome.schema.json $defs.outcome.enum (probe 1
    loads v1_outcome_enum.json / live schema via taxonomy.outcome_enum).
  * 6 variants from a fresh regex on WORK-UNIT-CATALOG.json (same source,
    independent parse).
  * Coverage via set algebra: enum - mapped keys, variants - mapped targets.
  * jsonschema over the 72 records built from the schema enum order.
Disagreement with the artifact's counts blocks the unit.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SCHEMA_PATH = HERE / "v1_outcome.schema.json"
MAPPING_PATH = HERE / "mapping.json"
ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0072-outcome-taxonomy-6-spec-variants-against-the-17-value-enum.md"
)
VARIANT_RE = re.compile(r"6 outcome variants\s*\(([^)]+)\)", re.IGNORECASE)
INVALID = {
    "id": "C-99",
    "artifact_type": "council-preset",
    "outcome": "PASS",
}


def canon(token: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (token or "").strip().lower()).strip("_")


def catalog_variants() -> list[str]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    q = ""
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "CNL-0072":
            q = str(u.get("question_or_target") or "")
            break
    m = VARIANT_RE.search(q)
    if not m:
        print("FAILED:CNL-0072-probe2 catalog variants parenthesis missing")
        raise SystemExit(1)
    parts = [p.strip() for p in m.group(1).split(",")]
    if len(parts) != 6:
        print(f"FAILED:CNL-0072-probe2 expected 6 variants got {parts}")
        raise SystemExit(1)
    return [canon(p) for p in parts]


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    enum_ids = list(schema["$defs"]["outcome"]["enum"])
    variant_ids = catalog_variants()
    map_doc = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    rows = [r for r in (map_doc.get("rows") or []) if isinstance(r, dict)]
    mapped_keys = [str(r["enum"]) for r in rows]
    mapped_targets = [str(r["variant"]) for r in rows if r.get("variant")]

    enum_set = set(enum_ids)
    var_set = set(variant_ids)
    key_set = set(mapped_keys)
    target_set = set(mapped_targets)

    missing_keys = sorted(enum_set - key_set)
    extra_keys = sorted(key_set - enum_set)
    missing_targets = sorted(var_set - target_set)
    extra_targets = sorted(target_set - var_set)
    variants_not_in_enum = sorted(var_set - enum_set)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    recs = []
    n = len(enum_ids)
    for i in range(1, 73):
        recs.append(
            {
                "id": f"C-{i:02d}",
                "artifact_type": "council-preset",
                "outcome": enum_ids[(i - 1) % n],
            }
        )
    good_errors = sum(len(list(validator.iter_errors(r))) for r in recs)
    bad_errs = list(validator.iter_errors(INVALID))
    used = {r["outcome"] for r in recs}
    outside_usage = sorted(used - enum_set)

    print(f"RECOUNT enum_n={len(enum_ids)} unique={len(enum_set)}")
    print(f"RECOUNT variant_n={len(variant_ids)} unique={len(var_set)}")
    print(
        f"SET missing_keys={missing_keys} extra_keys={extra_keys} "
        f"missing_targets={missing_targets} extra_targets={extra_targets} "
        f"variants_not_in_enum={variants_not_in_enum} outside_usage={outside_usage}"
    )
    print(f"RECOUNT good_error_count={good_errors} invalid_error_count={len(bad_errs)}")

    if len(enum_ids) != 17 or len(enum_set) != 17:
        print("FAILED:CNL-0072-probe2 enum recount is not 17 unique")
        return 1
    if len(variant_ids) != 6 or len(var_set) != 6:
        print("FAILED:CNL-0072-probe2 variant recount is not 6 unique")
        return 1
    if missing_keys or extra_keys or missing_targets or extra_targets:
        print("FAILED:CNL-0072-probe2 mapping is not a total function 17->6")
        return 1
    if variants_not_in_enum:
        print("FAILED:CNL-0072-probe2 spec variant missing from enum")
        return 1
    if outside_usage:
        print("FAILED:CNL-0072-probe2 synthetic usage outside enum")
        return 1
    if good_errors != 0:
        print("FAILED:CNL-0072-probe2 known-good not 0 errors")
        return 1
    if len(bad_errs) < 1:
        print("FAILED:CNL-0072-probe2 garbage outcome PASS was accepted")
        return 1

    garbage_docs = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"id": "C-01", "artifact_type": "council-preset"},
    )
    rejected = 0
    for g in garbage_docs:
        if list(validator.iter_errors(g)):
            rejected += 1
        else:
            print(f"FAILED:CNL-0072-probe2 schema accepted garbage {g}")
            return 1
    if rejected != 3:
        print("FAILED:CNL-0072-probe2 garbage rejected count")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("enum_17", {}).get("ids") != enum_ids:
            print("FAILED:CNL-0072-probe2 artifact enum disagreement")
            return 1
        art_vars = [v.get("id") for v in (doc.get("spec_variants_6") or [])]
        if art_vars != variant_ids:
            print("FAILED:CNL-0072-probe2 artifact variant disagreement")
            return 1
        if int(doc.get("schema_validation", {}).get("good_error_count", -1)) != 0:
            print("FAILED:CNL-0072-probe2 artifact good_error_count disagreement")
            return 1
        if int(doc.get("usage", {}).get("outside_count", -1)) != 0:
            print("FAILED:CNL-0072-probe2 artifact usage outside_count disagreement")
            return 1

    print(
        "NEGATIVE CONTROL verbatim: Draft202012Validator rejects outcome='PASS' "
        f"with error_count={len(bad_errs)}; it does not stay silent on a "
        "non-enum token, and it does not accept a record missing 'outcome'."
    )
    print("SUCCESS:CNL-0072-probe2 independent-recount set-algebra jsonschema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
