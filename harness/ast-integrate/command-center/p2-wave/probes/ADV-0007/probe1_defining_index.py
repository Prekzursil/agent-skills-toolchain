#!/usr/bin/env python3
"""Probe 1: id->definition index from DEFINING headings only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:{E.UNIT}-probe1 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    planted = E.fixture_corpus()
    p1 = E.probe1_index(planted)
    ctrl = E.control_probe1(p1)
    if not ctrl["pass"]:
        return fail("heading-cardinality control failed", ctrl)
    payload = {
        "pass": True,
        "probe": "probe1-defining-index",
        "unit_id": E.UNIT,
        "instrument": p1["instrument"],
        "definition_count": len(planted["definitions"]),
        "reference_count": len(planted["references"]),
        "multi_def_ids": p1["multi_def_ids"],
        "unique_ids": p1["unique_ids"],
        "rows": p1["rows"],
        "control": {
            "id": ctrl["id"],
            "pass": True,
            "ambiguous_id": ctrl["ambiguous_id"],
            "unambiguous_id": ctrl["unambiguous_id"],
            "ambiguous_flagged_multi_def": ctrl["ambiguous_flagged_multi_def"],
            "unambiguous_unique": ctrl["unambiguous_unique"],
            "ambiguous_definition_count": (ctrl["ambiguous_row"] or {}).get(
                "definition_count"
            ),
            "unambiguous_definition_count": (ctrl["unambiguous_row"] or {}).get(
                "definition_count"
            ),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"multi_def={p1['multi_def_ids']} unique={p1['unique_ids']} "
        f"ambiguous_defs={payload['control']['ambiguous_definition_count']}"
    )
    print(
        f"SUCCESS:{E.UNIT}-probe1 defining-heading index: "
        f"{E.AMBIGUOUS_ID} MULTI-DEF, {E.UNAMBIGUOUS_ID} UNIQUE"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
