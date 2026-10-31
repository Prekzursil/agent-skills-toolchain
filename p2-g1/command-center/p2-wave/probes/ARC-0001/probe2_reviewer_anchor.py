#!/usr/bin/env python3
"""Probe 2: independent reviewer regex + computed set-completeness.

A second heading regex (parenthetical-required, A(\\d{1,2})) must reproduce
the same candidate id set. Completeness is (mapped+folded+rejected+full-team)
== enumerated, computed from mapper rows, not narrated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import enumerator as E  # noqa: E402
import mapper as M  # noqa: E402

ROSTER = E.REPO / "command-center" / "phase3" / "ROSTER.json"


def main() -> int:
    snap = E.snapshot()
    author = E.ids_of(snap["headings"])
    reviewer = E.ids_of(snap["reviewer_headings"])
    matrix = list(snap["matrix_ids"])
    print(f"author={author}")
    print(f"reviewer={reviewer}")
    print(f"matrix={matrix}")
    if author != reviewer:
        print("FAILED:ARC-0001-probe2 reviewer regex disagreed with author")
        return 1
    if author != matrix:
        print("FAILED:ARC-0001-probe2 matrix disagreed with headings")
        return 1
    if not snap["agreed"]:
        print("FAILED:ARC-0001-probe2 snapshot.agreed is false")
        return 1

    mapped = M.map_candidates(snap)
    comp = mapped["completeness"]
    print(
        "completeness enumerated={enumerated} mapped={mapped} "
        "folded={folded} full_team={full_team} rejected={rejected} "
        "sum={sum} holds={holds}".format(**comp)
    )
    if not comp["holds"]:
        print("FAILED:ARC-0001-probe2 set-completeness does not hold")
        return 1
    if comp["enumerated"] != 11:
        print("FAILED:ARC-0001-probe2 enumerated != 11")
        return 1
    if comp["mapped"] + comp["rejected"] + comp["folded"] + comp["full_team"] != 11:
        print("FAILED:ARC-0001-probe2 arithmetic")
        return 1

    if ROSTER.is_file():
        roster = json.loads(ROSTER.read_text(encoding="utf-8"))
        live_ids = [r["candidate_id"] for r in roster.get("mappings") or []]
        if live_ids != author:
            print(f"FAILED:ARC-0001-probe2 roster mappings {live_ids} != {author}")
            return 1
        rcomp = roster.get("set_completeness") or {}
        if rcomp.get("holds") is not True:
            print("FAILED:ARC-0001-probe2 roster set_completeness.holds is not true")
            return 1
        print(f"roster mappings={live_ids} holds={rcomp.get('holds')}")
    else:
        print("roster absent during probe (emit not yet run); skipped roster check")

    print("SUCCESS:ARC-0001-probe2 reviewer-anchor set-completeness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
