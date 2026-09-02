#!/usr/bin/env python3
"""Probe 2: always-accept mutant must move FN; schema must reject garbage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

SCHEMA = REPO / "command-center/schema/telemetry-threshold-receipt.schema.json"
MUTANT = M.ALWAYS_ACCEPT_GATE


def _fn_rate(doc: dict, gate_id: str) -> float:
    for g in doc["gates"]:
        if g["id"] == gate_id:
            rate = g["false_negative"]["rate"]
            if rate is None:
                raise SystemExit(f"FAILED:REL-0019-probe2 {gate_id} FN not measured")
            return float(rate)
    raise SystemExit(f"FAILED:REL-0019-probe2 missing gate {gate_id}")


def main() -> int:
    base = M.compute(seed=M.DEFAULT_SEED)
    mut = M.compute(seed=M.DEFAULT_SEED, always_accept=MUTANT)
    base_fn = _fn_rate(base, MUTANT)
    mut_fn = _fn_rate(mut, MUTANT)
    n_bad = next(g["n_known_bad"] for g in base["gates"] if g["id"] == MUTANT)
    print(
        json.dumps(
            {
                "gate": MUTANT,
                "n_bad": n_bad,
                "base_fn": base_fn,
                "mutant_fn": mut_fn,
                "delta": mut_fn - base_fn,
            },
            sort_keys=True,
        )
    )
    if mut_fn <= base_fn:
        print("FAILED:REL-0019-probe2 always-accept FN did not increase")
        return 1
    if (mut_fn - base_fn) < 0.3:
        print("FAILED:REL-0019-probe2 FN delta too small to count as measurable")
        return 1
    if mut_fn < 0.99:
        print("FAILED:REL-0019-probe2 always-accept should miss every known-bad")
        return 1
    # Independent reviewer: base rates must match a fresh recompute.
    again = M.compute(seed=M.DEFAULT_SEED)
    if M.rates_signature(base) != M.rates_signature(again):
        print("FAILED:REL-0019-probe2 independent recompute diverged")
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "REL-0019", "state": "SUCCESS"},
    ]
    for g in garbage:
        if validator.is_valid(g):
            print(f"FAILED:REL-0019-probe2 schema accepted garbage {list(g)[:3]}")
            return 1
    print("schema_rejected_garbage=3")
    print("SUCCESS:REL-0019-probe2 always-accept FN shift and schema discrimination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
