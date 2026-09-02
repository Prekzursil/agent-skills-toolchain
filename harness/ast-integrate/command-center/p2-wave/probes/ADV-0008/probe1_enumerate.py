#!/usr/bin/env python3
"""Probe 1: enumerate contract clauses and map each to a TEST-REGISTRY test id.

Mechanically different from probe 2 (no scratch copy, no SYSTEM mutation, no
test execution). Static index only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:ADV-0008-probe1 {msg}")
    return 1


def main() -> int:
    data = H.enumerate_clauses()
    print(json.dumps(data, indent=2, sort_keys=True))
    live = data["live"]
    by_id = {c["id"]: c for c in data["clauses"]}

    if live["contract_present"] and data["n_clauses"] < 6:
        return _fail("live contract bound; fixture enumerator missing")
    if live["registry_present"] and data["n_clauses"] < 6:
        return _fail("live TEST-REGISTRY.json bound; fixture map missing")
    if data["n_clauses"] < 6:
        return _fail(f"expected >=6 fixture clauses, got {data['n_clauses']}")
    c1 = by_id.get("CLAUSE-C1")
    if not c1 or "test_missing_field_rejected" not in c1["mapped_tests"]:
        return _fail("CLAUSE-C1 must map to test_missing_field_rejected")
    c3 = by_id.get("CLAUSE-C3")
    if not c3 or "test_always_green" not in c3["mapped_tests"]:
        return _fail("CLAUSE-C3 planted decorative map missing")
    c5 = by_id.get("CLAUSE-C5")
    if not c5 or "test_does_not_exist" not in (c5.get("missing_tests") or []):
        return _fail("CLAUSE-C5 planted missing test was not flagged")
    c6 = by_id.get("CLAUSE-C6")
    if not c6 or c6["mapped"]:
        return _fail("CLAUSE-C6 must remain unmapped")
    if not all(c["atomic"] and c["text"] for c in data["clauses"]):
        return _fail("every enumerated clause must be an atomic MUST assertion")
    print(
        "clauses={n} mapped={m} unmapped={u} missing_tests={x}".format(
            n=data["n_clauses"],
            m=data["n_mapped"],
            u=data["n_unmapped"],
            x=data["n_missing_tests"],
        )
    )
    print("SUCCESS:ADV-0008-probe1 enumerate clauses and map TEST-REGISTRY ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
