#!/usr/bin/env python3
"""Named probe 2: JS round-trip of the widest field + schema forbids unbounded ints.

Positive: handled-ledger.mjs preserves uint64 id / ns timestamp / oversize
byte_count as decimal strings.
Negative: JSON.parse degrades those same numeric tokens.
Mutation: dropping seq.maximum makes the forbids-checker fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from tests import (  # noqa: E402
    WIDEST_ID,
    run_required_tests,
    test_large_integer_round_trips_through_the_js_consumer,
    test_schema_forbids_unbounded_integers_where_a_js_consumer_exists,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0056-probe2 {msg}")
    return 1


def main() -> int:
    try:
        rt = test_large_integer_round_trips_through_the_js_consumer()
        sch = test_schema_forbids_unbounded_integers_where_a_js_consumer_exists()
        rows = run_required_tests()
    except AssertionError as exc:
        return fail(str(exc))
    except Exception as exc:  # noqa: BLE001 — surface node/schema failures
        return fail(f"{type(exc).__name__}: {exc}")

    if rt.get("lossless_id") != str(WIDEST_ID):
        return fail("round-trip did not preserve widest id")
    if str(rt.get("naive_id_decimal")) == str(WIDEST_ID):
        return fail("JSON.parse negative control did not fire")
    if not sch.get("numeric_id_rejected") or not sch.get("oversize_seq_rejected"):
        return fail("schema did not reject unbounded integer forms")
    if int(sch.get("mutation_unbounded_after_drop_maximum") or 0) < 1:
        return fail("maximum-drop mutation did not trip the forbids-checker")

    payload = {
        "pass": True,
        "probe": "probe2-js-roundtrip-and-schema",
        "unit_id": "TST-0056",
        "tests": rows,
        "round_trip": rt,
        "schema_forbids": sch,
        "both_states": {
            "lossless_preserves_uint64": True,
            "json_parse_degrades_uint64": True,
            "drop_maximum_reds_forbids_checker": True,
        },
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    print(
        f"widest_id lossless={rt['lossless_id']} naive={rt['naive_id_decimal']} "
        f"schema_unbounded={sch['unbounded_integers_in_js_schema']}"
    )
    print("SUCCESS:TST-0056-probe2 JS round-trip; schema forbids unbounded ints")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
