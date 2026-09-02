#!/usr/bin/env python3
"""Probe 2: hidden-COI negative control and authorship-vs-vote cross-reference.

Starts from the tests, not the author's summary:

  * clean PCJ run -> cross-reference EMPTY and roster seated
  * constructed self-review roster -> roster REFUSED (refusal event)
  * allow_self_review mutant of that roster -> cross-reference FIRES
  * spec 11242 hidden class: empty declaration + author vote, mutant ->
    hidden detector FIRES; production path refuses the roster
  * undeclared (missing field) -> refused
  * both-states: an unconflicted voter on the same artifact still counts
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.integrity.coi import (  # noqa: E402
    Action,
    Artifact,
    Seat,
    authorship_action_crossref,
    detect_hidden_coi,
    simulate_run,
    validate_roster,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0277-probe2 {msg}")
    return 1


def main() -> int:
    seats = [
        Seat("P", {"proposer"}, declared_interests=[]),
        Seat("C", {"critic"}, declared_interests=[]),
        Seat("J", {"judge"}, declared_interests=[]),
        Seat("V", {"voter"}, declared_interests=[]),
    ]
    artifacts = [
        Artifact("prop-1", frozenset({"P"}), kind="proposal"),
        Artifact("obj-1", frozenset({"C"}), kind="objection"),
        Artifact("ruling-1", frozenset({"J"}), kind="ruling"),
    ]
    actions = [
        Action("P", "prop-1", "propose", counts=False),
        Action("C", "prop-1", "critique", counts=True),
        Action("C", "obj-1", "propose", counts=False),
        Action("J", "prop-1", "judge", counts=True),
        Action("V", "prop-1", "vote", counts=True),
    ]
    clean = simulate_run(seats, artifacts, actions)
    if not clean.ok or clean.roster.refused or clean.crossref:
        return fail(
            f"clean run not empty-crossref ok={clean.ok} "
            f"refused={clean.roster.refused} crossref={clean.crossref}"
        )
    voter_accepted = any(
        a.participant_id == "V" and a.kind == "vote" for a in clean.accepted_actions
    )
    if not voter_accepted:
        return fail("unconflicted voter ballot was not accepted (over-broad COI)")

    bad_seats = [
        Seat("P", {"proposer", "judge"}, declared_interests=[]),
        Seat("C", {"critic"}, declared_interests=[]),
        Seat("V", {"voter"}, declared_interests=[]),
    ]
    bad_arts = [Artifact("prop-1", frozenset({"P"}), kind="proposal")]
    bad_acts = [
        Action("P", "prop-1", "propose", counts=False),
        Action("P", "prop-1", "judge", counts=True),
        Action("V", "prop-1", "vote", counts=True),
    ]
    refused = simulate_run(bad_seats, bad_arts, bad_acts)
    if not refused.roster.refused:
        return fail("self-review roster was seated under production enforce")
    refusal_events = [
        e for e in refused.events if e.get("event") == "COI_ROSTER_REFUSED"
    ]
    if not refusal_events:
        return fail("self-review roster produced no COI_ROSTER_REFUSED event")

    mutant = simulate_run(bad_seats, bad_arts, bad_acts, allow_self_review=True)
    if mutant.roster.refused:
        return fail("mutant still refused the roster; negative control cannot FIRE")
    if not mutant.crossref:
        return fail("negative control: allow_self_review but crossref stayed silent")
    if not any(h.get("used_declaration_field") is False for h in mutant.crossref):
        return fail("crossref used the declaration field; hidden class not proven")

    hidden_seats = [
        Seat("P", {"proposer", "voter"}, declared_interests=[]),
        Seat("C", {"critic"}, declared_interests=[]),
        Seat("J", {"judge"}, declared_interests=[]),
    ]
    hidden_arts = [Artifact("prop-1", frozenset({"P"}), kind="proposal")]
    hidden_acts = [
        Action("P", "prop-1", "propose", counts=False),
        Action("C", "prop-1", "critique", counts=True),
        Action("J", "prop-1", "judge", counts=True),
        Action("P", "prop-1", "vote", counts=True),
    ]
    hidden_prod = simulate_run(hidden_seats, hidden_arts, hidden_acts)
    if not hidden_prod.roster.refused:
        return fail("hidden author-voter roster seated under production enforce")
    hidden_mutant = simulate_run(
        hidden_seats, hidden_arts, hidden_acts, allow_self_review=True
    )
    ledger = hidden_mutant.accepted_actions or hidden_acts
    hidden_hits = detect_hidden_coi(hidden_seats, hidden_arts, ledger)
    if not any(h.get("event") == "COI_HIDDEN_AUTHORSHIP" for h in hidden_hits):
        return fail("spec 11242 hidden class did not FIRE on empty declaration + vote")
    raw_join = authorship_action_crossref(hidden_arts, hidden_acts)
    if not raw_join:
        return fail("authorship join missed the planted author-vote")
    if any(h.get("used_declaration_field") for h in raw_join):
        return fail("authorship join consulted the declaration field")

    missing = validate_roster([Seat("X", {"voter"})], [])
    if not missing.refused:
        return fail("missing declared_interests was accepted")
    none = validate_roster(
        [Seat("Y", {"voter"}, declared_interests=[])],
        [Artifact("prop-1", frozenset({"P"}), kind="proposal")],
    )
    if none.refused:
        return fail("declared-none unconflicted voter was refused")

    summary = {
        "probe": "probe2-hidden-coi-negative-control",
        "unit_id": "IMP-0277",
        "clean_crossref_empty": True,
        "unconflicted_voter_counted": True,
        "self_review_roster_refused": True,
        "refusal_event": refusal_events[0],
        "negative_control_fired": True,
        "hidden_class_fired": True,
        "undeclared_refused": True,
        "declared_none_unconflicted_seated": True,
        "crossref_hits_on_mutant": mutant.crossref,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True, default=str))
    print(
        "clean_crossref=EMPTY self_review=REFUSED mutant_crossref=FIRED "
        "hidden_class=FIRED undeclared=REFUSED unconflicted_voter=COUNTED"
    )
    print("SUCCESS:IMP-0277-probe2 hidden-COI negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
