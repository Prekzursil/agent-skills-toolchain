#!/usr/bin/env python3
"""Probe 2: mid-run replacement inherits the role, not the predecessor position."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

OUT = REPO / "command-center/confirmation/CNF-0090-role-enforcement.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0090-probe2 {msg}")
    return 1


def main() -> int:
    council, rec = S.run_replacement(True)
    if not S.replacement_ok(rec):
        return fail(f"replacement contract broken {rec}")
    if rec["inherited_position"] is not None:
        return fail("replacement inherited predecessor position")
    if rec["predecessor"]["position"] != S.PREDECESSOR_BALLOT:
        return fail("predecessor position was not the distinctive ballot")
    if rec["replacement_position_after_vote"] != S.REPLACEMENT_BALLOT:
        return fail("replacement did not cast its own ballot")
    if rec["inherited_role_id"] != "voter":
        return fail("replacement did not inherit voter role")
    if not rec["inherited_mandate"]["vote"]:
        return fail("replacement lost vote rights")
    if S.PREDECESSOR_BALLOT in rec["replacement_ballots_after_vote"]:
        return fail("predecessor ballot leaked onto replacement")
    seat = council.seats[S.VOTER_SEAT]
    if seat.occupant_id != S.REPLACEMENT_ID:
        return fail("seat occupant was not replaced")

    if not OUT.is_file() or OUT.stat().st_size < 200:
        return fail("confirmation artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if doc.get("state") != "SUCCESS":
        return fail(f"artifact state={doc.get('state')}")
    attached = S.artifact_field(doc, "replacement_transcript") or {}
    if attached.get("replacement_occupant_id") != S.REPLACEMENT_ID:
        return fail("artifact replacement occupant mismatch")
    if attached.get("inherited_position") is not None:
        return fail("artifact claims position inheritance")
    if attached.get("replacement_position_after_vote") != S.REPLACEMENT_BALLOT:
        return fail("artifact replacement ballot mismatch")
    if (attached.get("predecessor") or {}).get("position") != S.PREDECESSOR_BALLOT:
        return fail("artifact predecessor position mismatch")

    out = {
        "probe": "probe2-replacement-inherits-role",
        "unit_id": "CNF-0090",
        "inherited_role_id": rec["inherited_role_id"],
        "inherited_position": rec["inherited_position"],
        "predecessor_position": rec["predecessor"]["position"],
        "replacement_ballot": rec["replacement_position_after_vote"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0090-probe2 replacement inherits role not position")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
