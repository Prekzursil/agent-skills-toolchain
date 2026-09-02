#!/usr/bin/env python3
"""Probe 1: dangling-reference control.

Copy the healthy fixture corpus, plant a $ref to a nonexistent contract,
and assert the checker reports that dangling edge. The healthy corpus
must stay silent on dangling so a planted hit is not a false positive
from a broken walker.
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
GHOST = "ARC-9999"


def main() -> int:
    if not FIXTURES.is_dir():
        print("FAILED:ARC-0105-probe1 fixture contracts missing")
        return 1
    healthy = C.scan_contracts_dir(FIXTURES)
    print(
        json.dumps(
            {
                "corpus": "healthy-fixtures",
                "present": healthy["counts"]["present"],
                "edges": healthy["counts"]["edges"],
                "dangling": healthy["counts"]["dangling"],
                "type_mismatches": healthy["counts"]["type_mismatches"],
                "consistent": healthy["consistent"],
            },
            sort_keys=True,
        )
    )
    if healthy["counts"]["present"] != 12:
        print(f"FAILED:ARC-0105-probe1 expected 12 fixtures got {healthy['counts']['present']}")
        return 1
    if healthy["counts"]["dangling"] != 0:
        print("FAILED:ARC-0105-probe1 healthy corpus already dangling; control is invalid")
        return 1
    if healthy["counts"]["edges"] < 4:
        print("FAILED:ARC-0105-probe1 healthy corpus has no cross-contract edges")
        return 1
    kinds = C.canonical_kinds_present(healthy)
    if not all(kinds.values()):
        print(f"FAILED:ARC-0105-probe1 missing canonical kinds {kinds}")
        return 1

    with tempfile.TemporaryDirectory(prefix="arc0105-dangling-") as tmp:
        planted = Path(tmp) / "contracts"
        C.copy_tree(FIXTURES, planted)
        C.plant_dangling(planted, ghost=GHOST)
        bad = C.scan_contracts_dir(planted)
        ghosts = [
            e
            for e in bad["dangling"]
            if e.get("to_contract") == GHOST
        ]
        print(
            json.dumps(
                {
                    "corpus": "planted-dangling",
                    "dangling": bad["counts"]["dangling"],
                    "ghost_hits": len(ghosts),
                    "ghost_ids": [e.get("to_contract") for e in ghosts],
                    "consistent": bad["consistent"],
                },
                sort_keys=True,
            )
        )
        if len(ghosts) < 1:
            print("FAILED:ARC-0105-probe1 planted dangling reference was not reported")
            return 1
        if bad["consistent"]:
            print("FAILED:ARC-0105-probe1 planted corpus marked consistent")
            return 1

    print("SUCCESS:ARC-0105-probe1 dangling-reference control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
