#!/usr/bin/env python3
"""Required TST-0056 tests: JS round-trip and schema bounds where JS consumes."""
from __future__ import annotations

import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft7Validator

from census import MAX_SAFE, REPO, integer_fields_unbounded

HERE = Path(__file__).resolve().parent
LEDGER_JS = REPO / "tools" / "lib" / "handled-ledger.mjs"
LEDGER_SCHEMA = REPO / "tools" / "lib" / "handled-ledger.schema.json"
NODE = os.environ.get("NODE", "node")

# Widest integer that fits uint64; JSON.parse degrades it.
WIDEST_ID = 2**64 - 1
# Unix ns around 2024-11; already above 2^53 (ulp at this magnitude is 256).
WIDEST_TS = 1_730_000_000_000_000_000
# First odd integer above MAX_SAFE; JSON.parse turns it into MAX_SAFE-... even.
WIDEST_BYTES = MAX_SAFE + 2
SEQ = 7


def node_cmd(cmd: str, text: str) -> str:
    proc = subprocess.run(
        [NODE, str(LEDGER_JS), cmd],
        input=text,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"node {cmd} rc={proc.returncode} stderr={(proc.stderr or '')[-800:]}"
        )
    return (proc.stdout or "").strip()


def numeric_wide_json() -> str:
    """JSON text with unquoted integer tokens (Python json keeps full precision)."""
    return json.dumps(
        {
            "id": WIDEST_ID,
            "timestamp_ns": WIDEST_TS,
            "byte_count": WIDEST_BYTES,
            "seq": SEQ,
        },
        separators=(",", ":"),
    )


def schema_valid_record() -> dict:
    return {
        "id": str(WIDEST_ID),
        "timestamp_ns": str(WIDEST_TS),
        "byte_count": str(WIDEST_BYTES),
        "seq": SEQ,
    }


def test_large_integer_round_trips_through_the_js_consumer() -> dict:
    if not LEDGER_JS.is_file():
        raise AssertionError("tools/lib/handled-ledger.mjs missing")
    text = numeric_wide_json()
    for token in (str(WIDEST_ID), str(WIDEST_TS), str(WIDEST_BYTES)):
        if f":{token}" not in text and f": {token}" not in text:
            raise AssertionError(f"numeric JSON missing unquoted token {token}")
        # Must be a JSON number, not a quoted string, so JS is at risk.
        if f'"{token}"' in text:
            raise AssertionError(f"token {token} is already a string")

    lossless = json.loads(node_cmd("roundtrip", text))
    if lossless.get("id") != str(WIDEST_ID):
        raise AssertionError(f"lossless id={lossless.get('id')!r} want {WIDEST_ID}")
    if lossless.get("timestamp_ns") != str(WIDEST_TS):
        raise AssertionError(
            f"lossless timestamp_ns={lossless.get('timestamp_ns')!r}"
        )
    if lossless.get("byte_count") != str(WIDEST_BYTES):
        raise AssertionError(f"lossless byte_count={lossless.get('byte_count')!r}")
    if lossless.get("seq") != SEQ:
        raise AssertionError(f"lossless seq={lossless.get('seq')!r}")

    naive = json.loads(node_cmd("naive", text))
    naive_id = naive.get("id")
    if str(naive_id) == str(WIDEST_ID):
        raise AssertionError(
            "negative control failed: JSON.parse preserved uint64 id "
            f"(got {naive_id!r})"
        )
    if str(naive.get("byte_count")) == str(WIDEST_BYTES):
        raise AssertionError(
            "negative control failed: JSON.parse preserved byte_count "
            f"{naive.get('byte_count')!r}"
        )
    return {
        "id": "test_large_integer_round_trips_through_the_js_consumer",
        "result": "PASS",
        "widest_field": "id",
        "widest_value": str(WIDEST_ID),
        "lossless_id": lossless.get("id"),
        "naive_id": naive_id,
        "naive_id_decimal": str(naive_id),
        "js_consumer": "tools/lib/handled-ledger.mjs",
    }


def test_schema_forbids_unbounded_integers_where_a_js_consumer_exists() -> dict:
    if not LEDGER_SCHEMA.is_file():
        raise AssertionError("tools/lib/handled-ledger.schema.json missing")
    schema = json.loads(LEDGER_SCHEMA.read_text(encoding="utf-8"))
    unbounded = integer_fields_unbounded(
        schema, "tools/lib/handled-ledger.schema.json"
    )
    if unbounded:
        raise AssertionError(
            "JS-consumed schema still has unbounded integers: "
            + json.dumps(unbounded)
        )
    validator = Draft7Validator(schema)
    good = schema_valid_record()
    good_errors = sorted(validator.iter_errors(good), key=lambda e: e.path.__str__())
    if good_errors:
        raise AssertionError(
            "schema-valid string-encoded record rejected: "
            + good_errors[0].message
        )

    as_number = dict(good)
    as_number["id"] = WIDEST_ID
    number_errors = list(validator.iter_errors(as_number))
    if not number_errors:
        raise AssertionError("schema accepted uint64 id as a JSON integer")

    big_seq = dict(good)
    big_seq["seq"] = MAX_SAFE + 1
    seq_errors = list(validator.iter_errors(big_seq))
    if not seq_errors:
        raise AssertionError("schema accepted seq above MAX_SAFE_INTEGER")

    mutated = deepcopy(schema)
    del mutated["properties"]["seq"]["maximum"]
    mutated_unbounded = integer_fields_unbounded(mutated, "<mutated>")
    if not mutated_unbounded:
        raise AssertionError(
            "forbids-checker silent after deleting seq.maximum (detector-failure)"
        )

    return {
        "id": "test_schema_forbids_unbounded_integers_where_a_js_consumer_exists",
        "result": "PASS",
        "js_consumed_schema": "tools/lib/handled-ledger.schema.json",
        "unbounded_integers_in_js_schema": 0,
        "numeric_id_rejected": True,
        "oversize_seq_rejected": True,
        "mutation_unbounded_after_drop_maximum": len(mutated_unbounded),
        "good_record_accepted": True,
    }


def run_required_tests() -> list[dict]:
    return [
        test_large_integer_round_trips_through_the_js_consumer(),
        test_schema_forbids_unbounded_integers_where_a_js_consumer_exists(),
    ]


if __name__ == "__main__":
    rows = run_required_tests()
    print(json.dumps({"tests": rows}, sort_keys=True))
    print("SUCCESS:TST-0056-tests")
