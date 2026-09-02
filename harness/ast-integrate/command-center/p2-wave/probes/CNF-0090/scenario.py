#!/usr/bin/env python3
"""CNF-0090 fixture: same scripted council, two mandate configurations, then replace."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from runtime import Council, Mandate, Seat

ROLES: dict[str, Mandate] = {
    "proposer": Mandate(speaking=True, vote=False, veto=False),
    "voter": Mandate(speaking=True, vote=True, veto=False),
    "critic": Mandate(speaking=True, vote=False, veto=False),
    "chair": Mandate(speaking=True, vote=True, veto=True),
    "observer": Mandate(speaking=False, vote=False, veto=False),
}

SEAT_SPEC: list[dict[str, str]] = [
    {
        "seat_id": "seat-proposer",
        "occupant_id": "alice-proposer",
        "role_id": "proposer",
    },
    {
        "seat_id": "seat-voter",
        "occupant_id": "bob-voter",
        "role_id": "voter",
    },
    {
        "seat_id": "seat-critic",
        "occupant_id": "cara-critic",
        "role_id": "critic",
    },
    {
        "seat_id": "seat-chair",
        "occupant_id": "drew-chair",
        "role_id": "chair",
    },
    {
        "seat_id": "seat-observer",
        "occupant_id": "erin-observer",
        "role_id": "observer",
    },
]

# Same attempted actions in both configurations. Distinctive payloads make
# collapse (identical accept-all behaviour) mechanically visible.
SCRIPT: list[tuple[str, str, str]] = [
    ("seat-proposer", "speak", "POSITION:SHIP-THE-WIDGET"),
    ("seat-voter", "speak", "POSITION:APPROVE-WIDGET-X"),
    ("seat-critic", "speak", "risks remain; the voter should vote no"),
    ("seat-chair", "speak", "agenda is the widget decision"),
    ("seat-observer", "speak", "I should not be heard in this round"),
    ("seat-proposer", "vote", "YES-FROM-PROPOSER"),
    ("seat-voter", "vote", "APPROVE-WIDGET-X"),
    ("seat-critic", "vote", "NO-FROM-CRITIC"),
    ("seat-chair", "vote", "APPROVE-WIDGET-X"),
    ("seat-observer", "vote", "YES-FROM-OBSERVER"),
    ("seat-proposer", "veto", "NO-VETO-FROM-PROPOSER"),
    ("seat-voter", "veto", "NO-VETO-FROM-VOTER"),
    ("seat-critic", "veto", "NO-VETO-FROM-CRITIC"),
    ("seat-chair", "veto", "BLOCK-UNSAFE"),
    ("seat-observer", "veto", "NO-VETO-FROM-OBSERVER"),
]

VOTER_SEAT = "seat-voter"
REPLACEMENT_ID = "zoe-replacement"
REPLACEMENT_BALLOT = "REJECT-WIDGET-X"
PREDECESSOR_BALLOT = "APPROVE-WIDGET-X"


def make_seats() -> list[Seat]:
    seats = []
    for spec in SEAT_SPEC:
        seats.append(
            Seat(
                seat_id=spec["seat_id"],
                occupant_id=spec["occupant_id"],
                role_id=spec["role_id"],
                mandate=ROLES[spec["role_id"]],
            )
        )
    return seats


def play_script(council: Council) -> None:
    for seat_id, action, payload in SCRIPT:
        council.attempt(seat_id, action, payload)


def run_config(config_id: str, enforce: bool) -> Council:
    council = Council(config_id, enforce, make_seats())
    play_script(council)
    return council


def run_replacement(enforce: bool = True) -> tuple[Council, dict[str, Any]]:
    council = Council("enforced-then-replace", enforce, make_seats())
    play_script(council)
    rec = council.replace(VOTER_SEAT, REPLACEMENT_ID)
    after = council.attempt(VOTER_SEAT, "vote", REPLACEMENT_BALLOT)
    rec = deepcopy(rec)
    rec["replacement_vote"] = after.as_dict()
    rec["replacement_position_after_vote"] = council.seats[VOTER_SEAT].position
    rec["replacement_ballots_after_vote"] = list(council.seats[VOTER_SEAT].ballots)
    rec["predecessor_ballot_still_on_replacement"] = (
        PREDECESSOR_BALLOT in council.seats[VOTER_SEAT].ballots
        and PREDECESSOR_BALLOT != REPLACEMENT_BALLOT
        and len(council.seats[VOTER_SEAT].ballots) > 1
    )
    return council, rec


def logs_measurably_different(enforced: Council, stripped: Council) -> dict[str, Any]:
    fp_e = enforced.fingerprint()
    fp_s = stripped.fingerprint()
    counts_e = enforced.accepted_counts()
    counts_s = stripped.accepted_counts()
    different = fp_e != fp_s
    return {
        "measurably_different": different,
        "metric": (
            "per-occupant action:accepted fingerprint plus accepted "
            "speak/vote/veto counts"
        ),
        "enforced_fingerprint": fp_e,
        "stripped_fingerprint": fp_s,
        "accepted_counts": {"enforced": counts_e, "stripped": counts_s},
        "delta_accepted_votes": counts_s["vote"] - counts_e["vote"],
        "delta_accepted_vetoes": counts_s["veto"] - counts_e["veto"],
        "delta_accepted_speaks": counts_s["speak"] - counts_e["speak"],
    }


def event_for(council: Council, occupant_id: str, action: str) -> dict[str, Any] | None:
    for ev in council.events:
        if ev.occupant_id == occupant_id and ev.action == action:
            return ev.as_dict()
    return None


def vote_blocked_at_runtime(enforced: Council) -> bool:
    """A participant without vote rights is refused at the action site."""
    proposer = event_for(enforced, "alice-proposer", "vote")
    critic = event_for(enforced, "cara-critic", "vote")
    observer = event_for(enforced, "erin-observer", "vote")
    voter = event_for(enforced, "bob-voter", "vote")
    if not proposer or not critic or not observer or not voter:
        return False
    if proposer["accepted"] or critic["accepted"] or observer["accepted"]:
        return False
    if proposer["reason"] != "vote-rights-denied":
        return False
    if not voter["accepted"]:
        return False
    if proposer["enforced_at"] != "runtime":
        return False
    return True


def mention_is_not_a_vote(enforced: Council) -> bool:
    """Critic prose that mentions voting is a speak, not a ballot."""
    speak = event_for(enforced, "cara-critic", "speak")
    vote = event_for(enforced, "cara-critic", "vote")
    if not speak or not vote:
        return False
    if not speak["accepted"]:
        return False
    if "vote" not in speak["payload"]:
        return False
    if vote["accepted"]:
        return False
    seat = enforced.seats["seat-critic"]
    return "NO-FROM-CRITIC" not in seat.ballots


def replacement_ok(rec: dict[str, Any]) -> bool:
    pred = rec["predecessor"]
    if pred["occupant_id"] == rec["replacement_occupant_id"]:
        return False
    if pred["position"] == rec["inherited_position"] and pred["position"] is not None:
        return False
    if rec["inherited_position"] is not None:
        return False
    if rec["inherited_ballots"]:
        return False
    if rec["inherited_role_id"] != pred["role_id"]:
        return False
    if rec["inherited_mandate"] != pred["mandate"]:
        return False
    if not rec["inherited_mandate"]["vote"]:
        return False
    vote = rec["replacement_vote"]
    if not vote["accepted"]:
        return False
    if rec["replacement_position_after_vote"] != REPLACEMENT_BALLOT:
        return False
    if rec["predecessor_ballot_still_on_replacement"]:
        return False
    if PREDECESSOR_BALLOT in rec["replacement_ballots_after_vote"]:
        return False
    return True


def run_cnf_0090() -> dict[str, Any]:
    enforced = run_config("enforced-mandates", True)
    stripped = run_config("stripped-mandates", False)
    comparison = logs_measurably_different(enforced, stripped)
    repl_council, repl = run_replacement(True)
    tests = [
        {
            "id": "action-log-divergence",
            "name": "Enforced vs stripped per-participant action logs differ",
            "result": "PASS" if comparison["measurably_different"] else "FAIL",
            "detail": (
                f"delta_votes={comparison['delta_accepted_votes']} "
                f"delta_vetoes={comparison['delta_accepted_vetoes']} "
                f"delta_speaks={comparison['delta_accepted_speaks']}"
            ),
        },
        {
            "id": "vote-blocked-at-runtime",
            "name": "Occupant without vote rights is blocked at the runtime, not instructed",
            "result": "PASS" if vote_blocked_at_runtime(enforced) else "FAIL",
            "detail": str(event_for(enforced, "alice-proposer", "vote")),
        },
        {
            "id": "replacement-inherits-role-not-position",
            "name": "Replacement inherits the seat mandate and not the predecessor position",
            "result": "PASS" if replacement_ok(repl) else "FAIL",
            "detail": (
                f"inherited_position={repl['inherited_position']!r} "
                f"replacement_ballot={repl['replacement_position_after_vote']!r} "
                f"predecessor={repl['predecessor']['position']!r}"
            ),
        },
        {
            "id": "use-vs-mention",
            "name": "Speaking that mentions a vote is not classified as a vote",
            "result": "PASS" if mention_is_not_a_vote(enforced) else "FAIL",
            "detail": str(event_for(enforced, "cara-critic", "speak")),
        },
        {
            "id": "stripped-role-collapse-control",
            "name": "Stripped configuration accepts the forbidden actions the enforced run blocks",
            "result": (
                "PASS"
                if (event_for(stripped, "alice-proposer", "vote") or {}).get("accepted")
                and (event_for(stripped, "erin-observer", "speak") or {}).get("accepted")
                and (event_for(stripped, "bob-voter", "veto") or {}).get("accepted")
                else "FAIL"
            ),
            "detail": "stripped control must actually collapse, or the detector is inert",
        },
    ]
    planted_collapse = both_stripped_collapse()
    planted_inherit = planted_position_inheritance()
    vote_leak = vote_leak_on_stripped(stripped)
    return {
        "enforced": enforced,
        "stripped": stripped,
        "replacement_council": repl_council,
        "replacement": repl,
        "comparison": comparison,
        "tests": tests,
        "negative_controls": {
            "both_stripped_collapse": planted_collapse,
            "planted_position_inheritance": planted_inherit,
            "vote_leak_on_stripped": vote_leak,
        },
    }


def both_stripped_collapse() -> dict[str, Any]:
    """Known-broken pair: two mandate-stripped runs must fingerprint-match."""
    a = run_config("stripped-a", False)
    b = run_config("stripped-b", False)
    return {
        "same_fingerprint": a.fingerprint() == b.fingerprint(),
        "fingerprint": a.fingerprint(),
        "collapse_detected": a.fingerprint() == b.fingerprint(),
    }


def planted_position_inheritance() -> dict[str, Any]:
    """Known-broken replace: occupant swap that keeps the predecessor position."""
    council = Council("planted-inherit-position", True, make_seats())
    play_script(council)
    seat = council.seats[VOTER_SEAT]
    predecessor_position = seat.position
    seat.occupant_id = REPLACEMENT_ID
    return {
        "inherited_position": seat.position,
        "predecessor_position": predecessor_position,
        "position_inherited": (
            seat.position is not None and seat.position == predecessor_position
        ),
    }


def vote_leak_on_stripped(stripped: Council) -> dict[str, Any]:
    """Known-broken: stripped mandates let a non-voter cast a counted ballot."""
    proposer = event_for(stripped, "alice-proposer", "vote")
    observer = event_for(stripped, "erin-observer", "vote")
    leaked = bool(
        proposer
        and observer
        and proposer.get("accepted")
        and observer.get("accepted")
    )
    return {"vote_leaked": leaked, "proposer": proposer, "observer": observer}


def artifact_field(doc: dict[str, Any], key: str, default: Any = None) -> Any:
    """Read a payload field from the receipt top-level or report body."""
    if key in doc and doc[key] not in (None, [], {}):
        return doc[key]
    rep = doc.get("report")
    if isinstance(rep, dict) and key in rep and rep[key] not in (None, [], {}):
        return rep[key]
    return default
