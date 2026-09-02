#!/usr/bin/env python3
"""Probe 1: every family oracle is deterministic on the same gold artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import case_id_for, write_fixtures  # noqa: E402
from families import FAMILIES  # noqa: E402
from oracle import evaluate_twice  # noqa: E402

FIXTURES = HERE / "fixtures"


def main() -> int:
    write_fixtures()
    rows = []
    fail = False
    for family in FAMILIES:
        fid = str(family["family_id"])
        cid = case_id_for(fid)
        gold = FIXTURES / fid / "good.json"
        twice = evaluate_twice(gold, fid, cid)
        ok = bool(twice["identical"] and twice["first"]["accept"])
        rows.append(
            {
                "family_id": fid,
                "identical": twice["identical"],
                "accept": twice["first"]["accept"],
                "reasons": twice["first"]["reasons"],
                "ok": ok,
            }
        )
        if not ok:
            fail = True
    print(json.dumps({"probe": "probe1-oracle-determinism", "rows": rows}, indent=2, sort_keys=True))
    n_ok = sum(1 for r in rows if r["ok"])
    print(f"families={len(rows)} deterministic_accept={n_ok}")
    if fail:
        print("FAILED:WFA-0112-probe1 oracle not deterministic or gold not accepted")
        return 1
    print("SUCCESS:WFA-0112-probe1 every oracle accepted gold twice with identical verdicts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
