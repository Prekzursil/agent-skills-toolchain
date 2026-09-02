#!/usr/bin/env python3
"""Probe 1: prep gate blocks an unprepared participant.

Positive control: a seat with notes, resolvable file anchors, and matching
Read tool-calls is allowed to speak. Negative: missing artifact and empty
artifact are both refused via UnpreparedError, and corroboration does not
fire (that detector is reserved for assertion-without-fetch).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
COUNCIL = REPO / "tools" / "council"
sys.path.insert(0, str(COUNCIL))

import scenario as S  # noqa: E402
from prep import PrepGate, UnpreparedError, before_turn  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0362.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0362-probe1 {msg}")
    return 1


def main() -> int:
    g = S.gate()
    cases = S.run_cases()
    print(json.dumps({k: cases[k] for k in sorted(cases) if k != "alice_reasons" and k != "carol_reasons" and k != "bob_reasons"}, sort_keys=True))

    if not cases["alice_allowed"] or not cases["alice_prepared"]:
        return fail("prepared alice was not allowed to speak")
    if cases["alice_corroboration_fired"]:
        return fail("alice corroboration fired on a real fetch log")
    if not cases["alice_notes_grounded"]:
        return fail("alice notes were not grounded in fetched source tokens")
    if cases["alice_resolved"] != 2:
        return fail(f"alice resolved {cases['alice_resolved']} anchors, want 2")
    if not cases["before_turn_alice_ok"]:
        return fail("before_turn refused a prepared speaker")

    if cases["bob_none_allowed"] or cases["bob_empty_allowed"]:
        return fail("unprepared bob was allowed to speak")
    if cases["bob_none_fired"] or cases["bob_empty_fired"]:
        return fail("unprepared bob incorrectly fired assertion-without-fetch")
    if not cases["unprepared_blocked"]:
        return fail("require_prepared(bob) did not raise UnpreparedError")

    blocked = False
    try:
        g.require_prepared("bob", S.bob_empty(), [])
    except UnpreparedError as exc:
        blocked = True
        if exc.verdict.allowed_to_speak:
            return fail("UnpreparedError verdict still allowed speaking")
        print(f"unprepared_reasons={exc.verdict.reasons}")
    if not blocked:
        return fail("empty artifact did not raise UnpreparedError")

    try:
        before_turn(
            g,
            {"participant_id": "bob"},
            artifacts={},
            logs={},
        )
        return fail("before_turn allowed bob with no artifact")
    except UnpreparedError:
        print("before_turn_bob_blocked=True")

    if not cases["eve_allowed"] or cases["eve_fired"]:
        return fail("URL participant with WebFetch was not allowed")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        if "SUCCESS:IMP-0362" not in text:
            return fail("receipt sentinel-absent")

    print("unprepared_blocked=True alice_allowed=True eve_url_allowed=True")
    print("SUCCESS:IMP-0362-probe1 prep gate blocks an unprepared participant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
