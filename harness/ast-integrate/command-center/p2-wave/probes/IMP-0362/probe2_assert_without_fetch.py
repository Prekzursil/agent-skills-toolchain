#!/usr/bin/env python3
"""Probe 2: assert preparation without fetching; corroboration must FIRE.

The falsifiable question: is preparation verified by an artifact + tool-call
log, or by the participant asserting they did the reading?

Planted bad states:
  * asserted_prepared=true, source named, zero tool-calls
  * same artifact with a Read whose status is 'asserted' (self-report)
  * URL artifact with no WebFetch

Control: the same asserted artifact plus a real Read of the named file must
NOT fire, and must grant the speaking turn.
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
from prep import AssertionWithoutFetchError, UnpreparedError  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0362.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0362-probe2 {msg}")
    return 1


def main() -> int:
    g = S.gate()
    carol = g.evaluate("carol", S.carol_asserted(), [])
    dave = g.evaluate("carol", S.carol_asserted(), S.dave_asserted_tool())
    eve_bare = g.evaluate("eve", S.eve_url_artifact(), [])
    fetched_ungrounded = g.evaluate("carol", S.carol_asserted(), S.alice_fetches()[:1])

    summary = {
        "carol_fired": carol.corroboration_fired,
        "carol_allowed": carol.allowed_to_speak,
        "dave_asserted_tool_fired": dave.corroboration_fired,
        "dave_asserted_tool_allowed": dave.allowed_to_speak,
        "eve_bare_fired": eve_bare.corroboration_fired,
        "eve_bare_allowed": eve_bare.allowed_to_speak,
        "fetched_ungrounded_fired": fetched_ungrounded.corroboration_fired,
        "fetched_ungrounded_allowed": fetched_ungrounded.allowed_to_speak,
        "fetched_ungrounded_notes_grounded": fetched_ungrounded.notes_grounded,
        "parse_asserted_is_not_fetch": not S.parse_tool_call(S.dave_asserted_tool()[0]).is_real_fetch(),
    }
    print(json.dumps(summary, sort_keys=True))
    print(f"carol_reasons={carol.reasons}")
    print(f"dave_reasons={dave.reasons}")

    if not carol.corroboration_fired:
        return fail("assert-without-fetch did not fire on empty tool log")
    if carol.allowed_to_speak:
        return fail("carol was allowed to speak without fetches")
    if not dave.corroboration_fired or dave.allowed_to_speak:
        return fail("asserted Read status was treated as a real fetch")
    if not eve_bare.corroboration_fired or eve_bare.allowed_to_speak:
        return fail("URL assertion without WebFetch did not fire")
    if not summary["parse_asserted_is_not_fetch"]:
        return fail("parse_tool_call treated asserted Read as a fetch")

    fired = False
    try:
        g.require_prepared("carol", S.carol_asserted(), [])
    except AssertionWithoutFetchError as exc:
        fired = True
        if not exc.verdict.corroboration_fired:
            return fail("AssertionWithoutFetchError verdict did not set corroboration_fired")
        print(f"require_prepared_fired={exc.verdict.summary()}")
    except UnpreparedError as exc:
        return fail(f"empty-log assertion raised UnpreparedError instead of corroboration: {exc}")
    if not fired:
        return fail("require_prepared did not raise AssertionWithoutFetchError")

    # Fetch without grounded notes: corroboration stays silent (they did fetch);
    # speaking is still refused because notes are not from the source.
    if fetched_ungrounded.corroboration_fired:
        return fail("real Read of brief.md still fired assertion-without-fetch")
    if fetched_ungrounded.allowed_to_speak or fetched_ungrounded.notes_grounded:
        return fail("ungrounded self-report notes were treated as preparation")
    print(f"fetched_ungrounded_reasons={fetched_ungrounded.reasons}")

    # Silent-on-good-state: alice fetched and wrote notes that quote the sources.
    alice = g.evaluate("alice", S.alice_artifact(), S.alice_fetches())
    if alice.corroboration_fired or not alice.allowed_to_speak:
        return fail(f"alice good-state was not silent/allowed: {alice.reasons}")
    print("good_state_alice_silent=True")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        if "SUCCESS:IMP-0362" not in text:
            return fail("receipt sentinel-absent")

    print("corroboration_fired=True asserted_tool_rejected=True good_state_silent=True")
    print("SUCCESS:IMP-0362-probe2 assert-without-fetch corroboration FIRES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
