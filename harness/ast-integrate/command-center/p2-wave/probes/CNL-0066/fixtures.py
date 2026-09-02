#!/usr/bin/env python3
"""CNL-0066 fixtures: principled, strategic, shrinking-PV, non-pivotal."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

SEATS_FIVE = [
    {"id": "s1", "expertise_tags": ["crypto"], "prior_positions": []},
    {"id": "s2", "expertise_tags": ["crypto"], "prior_positions": []},
    {"id": "s3", "expertise_tags": ["crypto"], "prior_positions": []},
    {"id": "s4", "expertise_tags": ["ops"], "prior_positions": []},
    {"id": "s5", "expertise_tags": ["crypto"], "prior_positions": []},
]

QUESTION_SEATED_4OF5 = {
    "id": "q-threshold-ratchet",
    "question_class_id": "protocol.threshold",
    "required_domains": ["crypto"],
    "seated_n0": 5,
    "threshold_yes": 4,
    "threshold_basis": "seated",
    "abstention_policy": "PARK_PRINCIPLED_ELSE_COUNT_AS_NO",
}

YES123_NO5 = [
    {"seat": "s1", "kind": "YES"},
    {"seat": "s2", "kind": "YES"},
    {"seat": "s3", "kind": "YES"},
    {"seat": "s5", "kind": "NO"},
]

PRINCIPLED_S4 = {
    "seat": "s4",
    "kind": "ABSTAIN",
    "reason_code": "NO_EXPERTISE",
    "missing_claim": {
        "what": "cryptographic security reduction for the proposed ratchet",
        "why_blocks_vote": (
            "ops seat cannot evaluate the reduction; a YES or NO would be unearned"
        ),
    },
    "would_unpark_if": {
        "field": "independent_crypto_review.status",
        "op": "eq",
        "value": "complete",
    },
}

STRATEGIC_S4 = {
    "seat": "s4",
    "kind": "ABSTAIN",
    "reason_code": "GENERIC",
    "missing_claim": None,
    "would_unpark_if": None,
}


def _council(
    name: str,
    question: dict,
    seats: list[dict],
    ballots: list[dict],
    expect: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": name,
        "question": copy.deepcopy(question),
        "seats": copy.deepcopy(seats),
        "ballots": copy.deepcopy(ballots),
        "expect": expect,
    }


def known_good_principled() -> dict[str, Any]:
    return _council(
        "known-good-principled",
        QUESTION_SEATED_4OF5,
        SEATS_FIVE,
        YES123_NO5 + [PRINCIPLED_S4],
        {
            "class": "PRINCIPLED",
            "strategic_fire": False,
            "decision": "PARKED",
            "yes": 3,
            "protocol_fired": False,
        },
    )


def planted_bad_strategic() -> dict[str, Any]:
    seats = copy.deepcopy(SEATS_FIVE)
    seats[3]["expertise_tags"] = ["crypto", "ops"]
    seats[3]["prior_positions"] = [
        {"question_class_id": "protocol.threshold", "kind": "YES"}
    ]
    return _council(
        "planted-bad-strategic",
        QUESTION_SEATED_4OF5,
        seats,
        YES123_NO5 + [STRATEGIC_S4],
        {
            "class": "STRATEGIC",
            "strategic_fire": True,
            "decision": "FAIL",
            "yes": 3,
            "protocol_fired": False,
        },
    )


def planted_bad_present_and_voting() -> dict[str, Any]:
    doc = planted_bad_strategic()
    doc["id"] = "planted-bad-present-and-voting"
    doc["question"]["threshold_basis"] = "present_and_voting"
    doc["expect"] = {
        "class": "STRATEGIC",
        "strategic_fire": True,
        "decision": "INVALID-PROTOCOL",
        "yes": 3,
        "protocol_fired": True,
    }
    return doc


def known_good_protocol() -> dict[str, Any]:
    doc = known_good_principled()
    doc["id"] = "known-good-protocol-seated-basis"
    return doc


def negative_nonpivotal_undetermined() -> dict[str, Any]:
    q = copy.deepcopy(QUESTION_SEATED_4OF5)
    q["threshold_yes"] = 3
    return _council(
        "negative-nonpivotal-generic",
        q,
        SEATS_FIVE,
        YES123_NO5 + [STRATEGIC_S4],
        {
            "class": "UNDETERMINED",
            "strategic_fire": False,
            "decision": "PASS",
            "yes": 3,
            "protocol_fired": False,
        },
    )


def all_fixtures() -> dict[str, dict[str, Any]]:
    return {
        "known-good-principled": known_good_principled(),
        "planted-bad-strategic": planted_bad_strategic(),
        "planted-bad-present-and-voting": planted_bad_present_and_voting(),
        "known-good-protocol-seated-basis": known_good_protocol(),
        "negative-nonpivotal-generic": negative_nonpivotal_undetermined(),
    }


def dump_fixtures() -> list[Path]:
    FIX.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, doc in all_fixtures().items():
        path = FIX / f"{name}.json"
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for p in dump_fixtures():
        print(p)
