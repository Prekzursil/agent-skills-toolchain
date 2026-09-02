#!/usr/bin/env python3
"""Probe 2: mutation control — non-idempotent replay must duplicate and go red.

Does not treat the artifact conclusion as evidence. Re-runs the mutant runner
and the torn-line loader, and checks that the schema rejects garbage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import schema_local as SL  # noqa: E402
import suite as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0443.json"
SCHEMA = REPO / "command-center/schema/run-ledger.schema.json"


def main() -> int:
    catalog = S.load_catalog()
    mutant = S.mutation_non_idempotent(catalog)
    torn = S.torn_last_line()
    print(
        "mutation_produced_duplicates="
        f"{mutant['produced_duplicates']} turned_test_red="
        f"{mutant['turned_test_red']} dups={mutant['duplicate_unit_ids'][:5]}..."
    )
    print(
        "torn_ok="
        f"{torn['ok']} kept={torn['kept']} "
        f"dropped_in_tail={torn['dropped_marker_only_in_tail']}"
    )
    checks = [
        ("mutation produced duplicates", mutant["produced_duplicates"] is True),
        ("mutation turned test red", mutant["turned_test_red"] is True),
        ("mutation ok", mutant["ok"] is True),
        ("torn last line absent", torn["ok"] is True),
        ("torn kept only complete record", torn["kept"] == ["IMP0443-TORN-KEEP"]),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:IMP-0443-probe2 {name}")
            return 1

    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        print("FAILED:IMP-0443-probe2 declared schema missing")
        return 1
    validator = SL.local_validator()
    garbage = (
        {},
        {"unit_id": "IMP-0443", "state": "SUCCESS"},
        {"blob": "x" * 200, "passing_tests": 999999},
    )
    for i, doc in enumerate(garbage):
        errs = list(validator.iter_errors(doc))
        print(f"garbage[{i}] rejected={bool(errs)}")
        if not errs:
            print("FAILED:IMP-0443-probe2 schema accepts garbage")
            return 1

    if not ART.is_file():
        print("FAILED:IMP-0443-probe2 run-ledger artifact missing")
        return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    reviewer = art.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        print("FAILED:IMP-0443-probe2 reviewer verdict not PASS")
        return 1
    if reviewer.get("independent") is not True:
        print("FAILED:IMP-0443-probe2 reviewer is not independent")
        return 1
    mut = art.get("mutation") or {}
    if mut.get("produced_duplicates") is not True or mut.get("turned_test_red") is not True:
        print("FAILED:IMP-0443-probe2 artifact mutation control not recorded")
        return 1
    print("SUCCESS:IMP-0443-probe2 mutation-control torn-line schema-garbage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
