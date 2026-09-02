#!/usr/bin/env python3
"""Probe 1: both-states control + one negative mutant per contract rule.

The catalog path command-center/schema/claim-record.schema.json is a generated
receipt-class shim. The eight-field claim contract lives in the unit-local
schema plus contract.validate_claim. Missing catalog required[] is a FINDING,
not a probe crash.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from contract import (  # noqa: E402
    CONTRACT_SCHEMA_REL,
    REQUIRED_FIELDS,
    SCHEMA_REL,
    both_states,
    catalog_schema_is_shim,
    contract_schema_required_fields,
    golden_claim,
    load_contract_schema,
    load_schema,
    mutate_blank,
    mutate_missing,
    negatives_per_rule,
    schema_required_fields,
    validate_claim,
)

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    catalog_required = schema_required_fields(REPO)
    missing_from_schema = [f for f in REQUIRED_FIELDS if f not in catalog_required]
    extra = [f for f in catalog_required if f not in REQUIRED_FIELDS]
    shim = catalog_schema_is_shim(REPO)
    print(f"schema={SCHEMA_REL}")
    print(f"schema_required={catalog_required}")
    print(f"catalog_fields_missing_from_schema={missing_from_schema}")
    print(f"schema_extra_required={extra}")
    print(f"catalog_schema_is_shim={shim}")

    contract_required = contract_schema_required_fields(REPO)
    contract_missing = [f for f in REQUIRED_FIELDS if f not in contract_required]
    print(f"contract_schema={CONTRACT_SCHEMA_REL}")
    print(f"contract_schema_required={contract_required}")
    if contract_missing:
        print(
            "FAILED:TST-0040-probe1 unit-local contract omitted a catalog field "
            f"{contract_missing}"
        )
        return 1

    contract_schema = load_contract_schema(REPO)
    contract_v = jsonschema.Draft7Validator(contract_schema)
    golden = golden_claim()
    py = validate_claim(golden)
    contract_errs = sorted(
        contract_v.iter_errors(golden), key=lambda e: list(e.path)
    )
    print(
        f"golden_contract_schema_errors={len(contract_errs)} "
        f"golden_python_ok={py['ok']}"
    )
    if contract_errs or not py["ok"]:
        for err in contract_errs[:8]:
            print(" ", list(err.path), err.message)
        print(" ", py["violations"])
        print("FAILED:TST-0040-probe1 golden claim rejected")
        return 1

    catalog_schema = load_schema(REPO)
    try:
        catalog_v = jsonschema.Draft7Validator(catalog_schema)
        catalog_errs = list(catalog_v.iter_errors(golden))
        print(f"golden_catalog_schema_errors={len(catalog_errs)}")
    except Exception as exc:  # noqa: BLE001 - unresolved $ref is a finding
        print(f"golden_catalog_schema_errors=unresolved:{type(exc).__name__}")

    missing_rec = mutate_missing("settling_experiment")
    blank_rec = mutate_blank("settling_experiment")
    missing_schema_errs = list(contract_v.iter_errors(missing_rec))
    blank_schema_errs = list(contract_v.iter_errors(blank_rec))
    if not missing_schema_errs:
        print("FAILED:TST-0040-probe1 contract schema accepted absent settling_experiment")
        return 1
    if not blank_schema_errs:
        print("FAILED:TST-0040-probe1 contract schema accepted blank settling_experiment")
        return 1

    control = both_states()
    print(json.dumps({k: control[k] for k in (
        "good_ok",
        "missing_ok",
        "blank_ok",
        "missing_rules",
        "blank_rules",
        "control_pass",
    )}, sort_keys=True))
    if not control["control_pass"]:
        print("FAILED:TST-0040-probe1 both-states control did not fire")
        return 1

    rows = negatives_per_rule()
    failed = [row for row in rows if row["ok"] or not row["fired"]]
    print(f"negatives={len(rows)} failed={len(failed)}")
    for row in rows:
        print(
            f"  {row['mutant']} rule={row['rule']} ok={row['ok']} "
            f"fired={row['fired']} rules={row['rules']}"
        )
    if failed:
        print("FAILED:TST-0040-probe1 a negative mutant did not fire")
        return 1

    covered = {row["rule"] for row in rows if row["fired"]}
    expect = {f"missing-{f}" for f in REQUIRED_FIELDS}
    expect.update({"invalid-verdict", "invalid-confidence_band", "same-probe-rerun"})
    if expect - covered:
        print(f"FAILED:TST-0040-probe1 uncovered rules {sorted(expect - covered)}")
        return 1

    print("SUCCESS:TST-0040-probe1 both-states and per-rule negatives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
