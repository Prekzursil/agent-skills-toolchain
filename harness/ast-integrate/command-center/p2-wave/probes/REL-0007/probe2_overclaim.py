#!/usr/bin/env python3
"""Probe 2: overclaim checker, mutation controls go red, reviewer re-run."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import controls as C  # noqa: E402
import jsonschema  # noqa: E402
import overclaim as O  # noqa: E402

ART = REPO / "command-center/receipts/REL-0007.json"
SCHEMA = REPO / "command-center/schema/release-gate-receipt.schema.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:REL-0007-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    ok, why = O.check_receipt(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:REL-0007-probe2 overclaim on live receipt")
        return 1

    garbage = [{}, {"passing_tests": 999999}, {"blob": "x" * 2000}]
    v = jsonschema.Draft7Validator(schema)
    for i, g in enumerate(garbage):
        errs = list(v.iter_errors(g))
        print(f"garbage[{i}] rejected={bool(errs)} n={len(errs)}")
        if not errs:
            print("FAILED:REL-0007-probe2 schema accepts garbage")
            return 1

    mutations = C.reviewer_mutations(doc)
    for m in mutations:
        print(f"mutation {m['id']} gate_red={m['gate_red']} why={m['why']}")
        if not m["gate_red"]:
            print(f"FAILED:REL-0007-probe2 mutation {m['id']} did not go red")
            return 1

    recorded = (
        (doc.get("reviewer") or {}).get("mutations_re_run")
        or (doc.get("report") or {}).get("mutations_re_run")
        or doc.get("mutations_re_run")
        or []
    )
    if len(recorded) < 3:
        print("FAILED:REL-0007-probe2 receipt omitted reviewer mutations")
        return 1
    print("SUCCESS:REL-0007-probe2 overclaim mutations reviewer-rerun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
