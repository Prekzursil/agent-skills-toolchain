"""Planted TST-0276 fixtures: silent, engaged, filler, and protocol-window."""
from __future__ import annotations

from typing import Any

from engagement import PROTOCOL_CONSENT_NO_OBJECTION, PROTOCOL_EXPLICIT_BALLOT

ROSTER_THREE = ["chair", "critic", "ghost"]
ROSTER_WINDOW = ["chair", "critic", "analyst"]


def _speak(seat: str, round_no: int, text: str, claims: list[str] | None = None) -> dict[str, Any]:
    act: dict[str, Any] = {
        "seat_id": seat,
        "round": round_no,
        "kind": "speak",
        "text": text,
    }
    if claims:
        act["claims"] = claims
    return act


def _vote(seat: str, round_no: int, ballot: str) -> dict[str, Any]:
    return {"seat_id": seat, "round": round_no, "kind": "vote", "ballot": ballot}


def silent_never_engaged() -> dict[str, Any]:
    """Planted silent seat: two engaged voters, ghost never acts."""
    return {
        "fixture_id": "silent-never-engaged",
        "protocol": PROTOCOL_EXPLICIT_BALLOT,
        "rounds": 2,
        "roster": list(ROSTER_THREE),
        "objection_window_round": 2,
        "acts": [
            _speak("chair", 1, "Ship the change.", ["ship"]),
            _speak("critic", 1, "Hold for tests.", ["hold"]),
            _vote("chair", 2, "yes"),
            _vote("critic", 2, "no"),
        ],
        "expected": {
            "absent": ["ghost"],
            "engaged": ["chair", "critic"],
            "agree": ["chair"],
            "numerator": 1,
            "denominator": 2,
            "figure": 0.5,
            "ghost_counted_as_agreeing": False,
            "escalation_fires": True,
            "inactivity_fires": True,
        },
    }


def ack_filler() -> dict[str, Any]:
    """Ghost only posts empty acks — must still fail the engagement floor."""
    spec = silent_never_engaged()
    spec["fixture_id"] = "ack-filler"
    spec["acts"] = list(spec["acts"]) + [
        _speak("ghost", 1, "ok"),
        _speak("ghost", 2, "ack"),
    ]
    spec["expected"] = {
        "absent": ["ghost"],
        "engaged": ["chair", "critic"],
        "agree": ["chair"],
        "numerator": 1,
        "denominator": 2,
        "figure": 0.5,
        "ghost_counted_as_agreeing": False,
        "escalation_fires": True,
        "reason_contains": "filler",
    }
    return spec


def engaged_clean() -> dict[str, Any]:
    """Both-states silent half: every seat speaks and votes."""
    return {
        "fixture_id": "engaged-clean",
        "protocol": PROTOCOL_EXPLICIT_BALLOT,
        "rounds": 2,
        "roster": ["chair", "critic", "analyst"],
        "objection_window_round": 2,
        "acts": [
            _speak("chair", 1, "Ship the change.", ["ship"]),
            _speak("critic", 1, "Hold for tests.", ["hold"]),
            _speak("analyst", 1, "Need a rollback plan.", ["rollback"]),
            _vote("chair", 2, "yes"),
            _vote("critic", 2, "no"),
            _vote("analyst", 2, "yes"),
        ],
        "expected": {
            "absent": [],
            "engaged": ["chair", "critic", "analyst"],
            "agree": ["chair", "analyst"],
            "numerator": 2,
            "denominator": 3,
            "figure": 2 / 3,
            "escalation_fires": False,
            "inactivity_fires": False,
        },
    }


def protocol_window(protocol: str) -> dict[str, Any]:
    """Same ledger, two protocols: analyst is engaged but silent in the window."""
    return {
        "fixture_id": f"protocol-window:{protocol}",
        "protocol": protocol,
        "rounds": 2,
        "roster": list(ROSTER_WINDOW),
        "objection_window_round": 2,
        "acts": [
            _speak("chair", 1, "Ship the change.", ["ship"]),
            _speak("critic", 1, "Also ship.", ["ship"]),
            _speak("analyst", 1, "I am present and have a claim.", ["present"]),
            _vote("chair", 2, "yes"),
            _vote("critic", 2, "yes"),
            # analyst: engaged via round-1 claim; silent in decision window
        ],
        "expected": (
            {
                "absent": [],
                "engaged": ["chair", "critic", "analyst"],
                "agree": ["chair", "critic"],
                "analyst_role": "ABSTAIN",
                "numerator": 2,
                "denominator": 3,
                "figure": 2 / 3,
            }
            if protocol == PROTOCOL_EXPLICIT_BALLOT
            else {
                "absent": [],
                "engaged": ["chair", "critic", "analyst"],
                "agree": ["chair", "critic", "analyst"],
                "analyst_role": "NO_OBJECTION",
                "numerator": 3,
                "denominator": 3,
                "figure": 1.0,
            }
        ),
    }


def all_specs() -> list[dict[str, Any]]:
    return [
        silent_never_engaged(),
        ack_filler(),
        engaged_clean(),
        protocol_window(PROTOCOL_EXPLICIT_BALLOT),
        protocol_window(PROTOCOL_CONSENT_NO_OBJECTION),
    ]
