#!/usr/bin/env python3
"""Named probe 1: exact roster round trip.

Requested identities come back as the seated set. Order may change in the
set view; the exact path still seats every named participant and no one else.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.participants.select_explicit import (  # noqa: E402
    compare_rosters_as_set,
    fixture_dir,
    load_roster_fixture,
    resolve_explicit,
    roster_set_equals,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0266-probe1 {msg}")
    return 1


def main() -> int:
    lookup, seats = load_roster_fixture(fixture_dir() / "known-good-roster.json")
    result = resolve_explicit(seats, lookup)
    if not result.ok:
        return fail(f"exact path refused known-good roster: {result.as_dict()}")
    if result.auto_substitution:
        return fail("exact path set auto_substitution")
    if result.substitutions:
        return fail(f"exact path substituted: {result.substitutions}")
    if result.refusals:
        return fail(f"exact path refused: {result.refusals}")
    ordered = result.seated_ids()
    requested = result.requested
    if ordered != requested:
        return fail(f"ordered round trip drifted {ordered} != {requested}")
    if not roster_set_equals(requested, ordered):
        return fail("set comparison failed on exact round trip")
    cmp = compare_rosters_as_set(requested, result.seated)
    if not cmp["equal"] or cmp["missing"] or cmp["extra"]:
        return fail(f"set diff on known-good: {cmp}")
    if len(ordered) != 3:
        return fail(f"expected 3 seats, got {ordered}")
    for seat, seated in zip(seats, result.seated):
        if seated.role != seat.role:
            return fail(f"role drift for {seat.participant_id}")
        if seated.substituted:
            return fail(f"substituted flag on {seated.participant_id}")

    payload = {
        "probe": "probe1-exact-round-trip",
        "unit_id": "IMP-0266",
        "requested": list(requested),
        "seated": list(ordered),
        "set_equals": True,
        "substitutions": 0,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "round_trip=True set_equals=True substitutions=0 "
        f"seated={list(ordered)}"
    )
    print("SUCCESS:IMP-0266-probe1 exact roster round trip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
