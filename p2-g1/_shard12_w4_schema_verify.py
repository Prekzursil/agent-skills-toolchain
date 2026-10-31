#!/usr/bin/env python3
"""Shard-12 wave-4 verification: schema-validate artifacts + receipts for 12 RES units.

TWO INSTRUMENTS, DIFFERENT ROLES (measured 2026-10-26, shard-12 w4):
  * receipt-core (receipt.schema.json) IS a closure instrument: 0-error required.
  * strict artifact-vs-class-profile conformance (artifact-class-profiles.schema.json)
    is CENSUS-ONLY, not the delivery gate. Program-wide historical drift: earlier-wave
    closed units fail it too (RES-0001 x16, RES-0003 x1, RES-0036 x1, RES-0101 x1,
    RES-0108 x1, RES-0094 x1; RES-0048/RES-0100 pass). The delivery gate is
    command-center/p2-wave/_measure_one_delivered.py (parse + sentinel + probes exit 0
    + manifest sha). A FAILED row below is therefore a census finding, not a delivery
    failure.
Fail-closed within its own scope: any validation error or resolver failure is a FAILED row.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(REPO / "platform" / "lib"))
sys.path.insert(0, str(REPO))

from jsonschema import Draft202012Validator  # noqa: E402

import schema_resolver as sr  # noqa: E402

UNITS = [
    "RES-0044", "RES-0049", "RES-0077", "RES-0079", "RES-0086", "RES-0089",
    "RES-0091", "RES-0102", "RES-0103", "RES-0111", "RES-0112", "RES-0114",
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    reg_data = sr.load_registry()
    receipt_schema = load(
        REPO / "platform" / "schema" / "receipt.schema.json"
    )
    receipt_val = Draft202012Validator(receipt_schema)
    failures = 0
    for uid in UNITS:
        cat = None
        for u in load(REPO / "command-center" / "WORK-UNIT-CATALOG.json")["work_units"]:
            if u.get("id") == uid:
                cat = u
                break
        if cat is None:
            print(f"FAILED:{uid} catalog-missing")
            failures += 1
            continue
        art_path = REPO / cat["output_path"]
        art = load(art_path)
        try:
            resolved = sr.resolve(cat.get("output_schema"), reg_data)
            phys = json.loads(Path(resolved.physical_path).read_text(encoding="utf-8"))
            if resolved.physical_fragment:
                node = phys
                for part in resolved.physical_fragment.lstrip("#/").split("/"):
                    node = node[part.replace("~1", "/").replace("~0", "~")]
                phys = node
            v = Draft202012Validator(phys)
            errs = sorted(v.iter_errors(art), key=lambda e: e.path)
            if errs:
                for e in errs[:3]:
                    print(f"  ERR {uid} at {list(e.path)}: {e.message[:160]}")
                print(f"FAILED:{uid} class-profile-CENSUS-drift errors={len(errs)} (delivery gate unaffected)")
                failures += 1
                continue
            schema_row = f"class-profile-CENSUS-ok ({resolved.artifact_class or resolved.kind})"
        except Exception as exc:  # noqa: BLE001 - fail closed, name the failure
            print(f"FAILED:{uid} schema-resolver: {type(exc).__name__}: {exc}")
            failures += 1
            continue
        rec_path = REPO / "command-center" / "receipts" / f"{uid}.json"
        rec = load(rec_path)
        rerrs = sorted(receipt_val.iter_errors(rec), key=lambda e: e.path)
        if rerrs:
            for e in rerrs[:3]:
                print(f"  ERR {uid} receipt at {list(e.path)}: {e.message[:160]}")
            print(f"FAILED:{uid} receipt-invalid errors={len(rerrs)}")
            failures += 1
            continue
        gate = "owner-gated" if cat.get("owner_approval_required") else "not-owner-gated"
        print(f"SUCCESS:{uid} {schema_row}; receipt-core-ok; {gate}")
    print(f"--- summary: {len(UNITS) - failures}/{len(UNITS)} census-conform; delivery gate = _measure_one_delivered.py")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
