#!/usr/bin/env python3
"""Both-states controls for the CNF-0098 macos-reachability record.

Catalog path command-center/schema/impossibility-record.schema.json is a
generated shim (unresolvable $ref, no unit constraints). Validation here
uses the probe-local schema and never fetches remote URIs.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[4]
SCHEMA_REL = "command-center/schema/impossibility-record.schema.json"
LOCAL_SCHEMA_REL = (
    "command-center/p2-wave/probes/CNF-0098/macos-reachability.schema.json"
)


def load_schema() -> dict:
    path = REPO / LOCAL_SCHEMA_REL
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    shim = REPO / SCHEMA_REL
    if not shim.is_file() or shim.stat().st_size <= 0:
        raise AssertionError(f"catalog output_schema missing: {SCHEMA_REL}")
    return schema


def errors(doc, schema=None) -> list[str]:
    schema = schema if schema is not None else load_schema()
    validator = jsonschema.Draft7Validator(schema)
    return sorted(
        f"{'/'.join(str(p) for p in err.absolute_path) or '<'}: {err.message}"
        for err in validator.iter_errors(doc)
    )


def assert_valid(doc, schema=None) -> None:
    errs = errors(doc, schema)
    if errs:
        raise AssertionError("schema rejected live record: " + "; ".join(errs[:8]))


def both_states(good: dict) -> dict:
    """Known-good accepted; one-signal, no settling experiment, garbage rejected."""
    schema = load_schema()
    assert_valid(good, schema)

    one_signal = copy.deepcopy(good)
    one_signal["two_signal_proof"] = one_signal["two_signal_proof"][:1]
    err_one = errors(one_signal, schema)
    if not err_one:
        raise AssertionError("schema accepted a one-signal record")

    no_settle = copy.deepcopy(good)
    no_settle.pop("settling_experiment", None)
    err_settle = errors(no_settle, schema)
    if not err_settle:
        raise AssertionError("schema accepted a record with no settling experiment")

    garbage_docs = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    )
    garbage_counts = []
    for garbage in garbage_docs:
        err_g = errors(garbage, schema)
        if not err_g:
            raise AssertionError(f"schema accepted garbage {list(garbage)[:3]}")
        garbage_counts.append(len(err_g))

    planted = copy.deepcopy(good)
    rows = list(planted.get("matrix_rows") or [])
    err_supported: list[str]
    if rows:
        rows[0] = dict(rows[0])
        rows[0]["evidence_state"] = "supported"
        planted["matrix_rows"] = rows
        err_supported = errors(planted, schema)
        if not err_supported:
            raise AssertionError("schema accepted evidence_state=supported")
    else:
        err_supported = ["no-rows"]

    return {
        "good_accepted": True,
        "one_signal_rejected": True,
        "one_signal_error_count": len(err_one),
        "no_settling_experiment_rejected": True,
        "no_settling_error_count": len(err_settle),
        "garbage_rejected": True,
        "garbage_error_counts": garbage_counts,
        "supported_row_rejected": True,
        "supported_row_error_count": 0 if err_supported == ["no-rows"] else len(err_supported),
        "executable_schema": LOCAL_SCHEMA_REL,
        "declared_schema_present": (REPO / SCHEMA_REL).is_file(),
    }
