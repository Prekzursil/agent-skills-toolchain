#!/usr/bin/env python3
"""Probe 1: static scan of every production raise/throw site.

Independent signal (1): AST walk. A planted uncoded raise in a temp tree
must be caught (both-states). The live plugin tree must have zero uncoded
sites. A declared taxonomy with no raise sites at all is a vacuous green.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import error_taxonomy as et  # noqa: E402

UNIT = "IMP-0051"


def main() -> int:
    live = et.uncoded_sites()
    all_sites = et.scan_raise_sites()
    coded = [s for s in all_sites if s.coded]
    if live:
        print("FAILED:IMP-0051-probe1 live uncoded raises")
        print(json.dumps([s.__dict__ for s in live], indent=2)[:4000])
        return 1
    if not coded:
        print("FAILED:IMP-0051-probe1 scanner saw zero coded raises (vacuous)")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0051-p1-") as td:
        planted = Path(td) / "planted.py"
        planted.write_text(
            "def boom():\n    raise RuntimeError('uncoded-plant')\n",
            encoding="utf-8",
        )
        caught = et.uncoded_sites(Path(td))
        if not caught:
            print("FAILED:IMP-0051-probe1 planted uncoded raise was not caught")
            return 1

    out = {
        "probe": "probe1-static-scan",
        "unit_id": UNIT,
        "pass": True,
        "live_uncoded": 0,
        "live_coded_raises": len(coded),
        "planted_uncoded_caught": len(caught),
        "both_states": True,
        "schema_errors": et.validate_against_schema(),
        "families_with_room": {
            fam: row["room"] for fam, row in et.family_numbering_gaps().items()
        },
    }
    if out["schema_errors"]:
        print("FAILED:IMP-0051-probe1 schema")
        print(json.dumps(out, indent=2))
        return 1
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0051-probe1 static scan clean; planted uncoded raise caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
