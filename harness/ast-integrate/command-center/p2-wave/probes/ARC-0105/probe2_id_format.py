#!/usr/bin/env python3
"""Probe 2: id-format consistency.

Every resolved cross-contract id field must share the target contract's
declared pattern. The healthy fixture corpus must show that match. A
planted local pattern that disagrees with ARC-0083's workUnitId must be
reported as type_mismatch.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checker as C  # noqa: E402

FIXTURES = HERE / "fixtures" / "contracts"


def main() -> int:
    if not FIXTURES.is_dir():
        print("FAILED:ARC-0105-probe2 fixture contracts missing")
        return 1
    healthy = C.scan_contracts_dir(FIXTURES)
    ok = healthy.get("ok_edges") or []
    mismatches = healthy.get("type_mismatches") or []
    print(
        json.dumps(
            {
                "corpus": "healthy-fixtures",
                "ok_edges": len(ok),
                "type_mismatches": len(mismatches),
                "pairs": [
                    {
                        "from": e["from_contract"],
                        "field": e["field"],
                        "to": e["to_contract"],
                        "source_pattern": e.get("source_pattern"),
                        "target_pattern": e.get("target_pattern"),
                        "status": e["status"],
                    }
                    for e in ok
                ],
            },
            sort_keys=True,
        )
    )
    if len(ok) < 4:
        print("FAILED:ARC-0105-probe2 expected at least 4 resolved edges")
        return 1
    if mismatches:
        print("FAILED:ARC-0105-probe2 healthy corpus has type mismatches")
        return 1
    for e in ok:
        if e.get("source_pattern") != e.get("target_pattern"):
            print(
                f"FAILED:ARC-0105-probe2 pattern not shared "
                f"{e['from_contract']}.{e['field']}"
            )
            return 1
        if not e.get("target_pattern"):
            print(f"FAILED:ARC-0105-probe2 missing target pattern {e}")
            return 1

    with tempfile.TemporaryDirectory(prefix="arc0105-mismatch-") as tmp:
        planted = Path(tmp) / "contracts"
        C.copy_tree(FIXTURES, planted)
        C.plant_pattern_mismatch(planted)
        bad = C.scan_contracts_dir(planted)
        hits = [
            e
            for e in (bad.get("type_mismatches") or [])
            if e.get("from_contract") == "ARC-0086"
            and e.get("field") == "unit_id"
            and e.get("to_contract") == "ARC-0083"
        ]
        print(
            json.dumps(
                {
                    "corpus": "planted-mismatch",
                    "type_mismatches": bad["counts"]["type_mismatches"],
                    "unit_id_hits": len(hits),
                    "consistent": bad["consistent"],
                },
                sort_keys=True,
            )
        )
        if len(hits) < 1:
            print("FAILED:ARC-0105-probe2 planted id-format mismatch was not reported")
            return 1
        if bad["consistent"]:
            print("FAILED:ARC-0105-probe2 planted corpus marked consistent")
            return 1

    print("SUCCESS:ARC-0105-probe2 id-format consistency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
