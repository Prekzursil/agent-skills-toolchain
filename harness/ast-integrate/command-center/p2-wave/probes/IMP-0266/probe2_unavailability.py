#!/usr/bin/env python3
"""Named probe 2: unavailability refusal + auto-substitution set-comparison FAIL.

Reviewer obligation starts from the tests, not the author's summary:
  * the unavailability fixture must produce a refusal event naming dom-cara
  * enabling auto-substitution must make set comparison FAIL
  * the known-good twin must still set-compare equal (silent on good state)
Exact path must not seat a substitute for the named unavailable participant.
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
    resolve_with_auto_substitution,
    roster_set_equals,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0266-probe2 {msg}")
    return 1


def main() -> int:
    good_lookup, good_seats = load_roster_fixture(
        fixture_dir() / "known-good-roster.json"
    )
    bad_lookup, bad_seats = load_roster_fixture(
        fixture_dir() / "unavailability.json"
    )

    good = resolve_explicit(good_seats, good_lookup)
    if not good.ok or not good.set_equals():
        return fail(f"known-good twin flipped: {good.as_dict()}")

    refused = resolve_explicit(bad_seats, bad_lookup)
    if refused.ok:
        return fail("exact path seated an unavailable named participant")
    if refused.seated:
        return fail(f"exact path returned a partial roster {refused.seated_ids()}")
    if len(refused.refusals) != 1:
        return fail(f"expected one refusal, got {refused.refusals}")
    event = refused.refusals[0]
    if event.get("kind") != "participant-unavailable":
        return fail(f"refusal kind {event.get('kind')}")
    if event.get("participant_id") != "dom-cara":
        return fail(f"refusal did not name dom-cara: {event}")
    if event.get("participant_named") is not True:
        return fail("refusal did not mark participant_named")
    if event.get("substituted") is not False:
        return fail("exact path marked substituted")
    if event.get("reason") != "unavailable":
        return fail(f"reason {event.get('reason')}")
    if "dom-cara" not in (event.get("requested_roster") or []):
        return fail("requested roster omitted the named unavailable participant")

    swapped = resolve_with_auto_substitution(bad_seats, bad_lookup)
    if not swapped.ok:
        return fail(f"auto-sub twin failed to seat: {swapped.as_dict()}")
    if not swapped.substitutions:
        return fail("auto-sub twin did not record a substitution")
    if swapped.substitutions[0].requested_id != "dom-cara":
        return fail("auto-sub swapped the wrong requested id")
    if swapped.substitutions[0].seated_id != "dom-drew":
        return fail(
            f"auto-sub seated {swapped.substitutions[0].seated_id}, want dom-drew"
        )
    if "dom-cara" in swapped.seated_ids():
        return fail("auto-sub still listed the unavailable name as seated")
    if roster_set_equals(swapped.requested, swapped.seated_ids()):
        return fail("set comparison PASSed after auto-substitution (detector silent)")
    cmp = compare_rosters_as_set(swapped.requested, swapped.seated_ids())
    if cmp["equal"]:
        return fail(f"compare_rosters_as_set equal after swap: {cmp}")
    if "dom-cara" not in cmp["missing"] or "dom-drew" not in cmp["extra"]:
        return fail(f"set diff did not show cara->drew: {cmp}")

    payload = {
        "probe": "probe2-unavailability",
        "unit_id": "IMP-0266",
        "refusal_names": event["participant_id"],
        "exact_seated": list(refused.seated_ids()),
        "exact_set_equals": refused.set_equals(),
        "good_twin_set_equals": good.set_equals(),
        "auto_sub_seated": list(swapped.seated_ids()),
        "auto_sub_set_equals": swapped.set_equals(),
        "set_comparison_failed_on_auto_sub": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "refusal_names=dom-cara exact_empty=True auto_sub_set_equals=False "
        "good_twin_set_equals=True"
    )
    print(
        "SUCCESS:IMP-0266-probe2 unavailability refusal and "
        "auto-substitution set-comparison FAIL"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
