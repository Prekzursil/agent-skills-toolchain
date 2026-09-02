"""Three fixtures for CNF-0092.

The question is deliberately obvious so the trigger is scored on PROCESS
(briefs / evidence / round), not on difficulty. Instant clones who happen
to be correct still fire. Independent briefs with evidence stay silent.
"""
from __future__ import annotations

QUESTION = (
    "Does the Python expression (1 + 1) == 2 evaluate to True? "
    "Answer YES or NO."
)

INSTANT_UNANIMITY = {
    "id": "instant-unanimity-clones",
    "title": "Round-1 clones, zero briefs, zero evidence",
    "question": QUESTION,
    "expected_trigger": True,
    "class": "known-broken",
    "participants": [
        {"id": "clone-a", "role": "clone", "vote": "YES", "brief": {}},
        {"id": "clone-b", "role": "clone", "vote": "YES", "brief": {}},
        {"id": "clone-c", "role": "clone", "vote": "YES", "brief": {}},
        {"id": "clone-d", "role": "clone", "vote": "YES", "brief": {}},
    ],
}

CONTESTED = {
    "id": "contested-split",
    "title": "Genuinely contested round-1 ballots",
    "question": QUESTION,
    "expected_trigger": False,
    "class": "negative-control",
    "participants": [
        {
            "id": "advocate",
            "role": "advocate",
            "vote": "YES",
            "brief": {
                "text": "Literal evaluation of (1+1)==2 is True.",
                "evidence_nodes": ["python:operator.eq", "int-addition"],
            },
        },
        {
            "id": "skeptic",
            "role": "skeptic",
            "vote": "NO",
            "brief": {
                "text": "Refuse to treat the identity as proven without a runtime sample.",
                "evidence_nodes": ["missing-runtime-sample"],
            },
        },
        {
            "id": "pragmatist",
            "role": "pragmatist",
            "vote": "YES",
            "brief": {
                "text": "Every CPython I can name returns True.",
                "evidence_nodes": ["cpython-eval"],
            },
        },
        {
            "id": "user-proxy",
            "role": "user-proxy",
            "vote": "REWORK",
            "brief": {
                "text": "Ask for a recorded eval before closing.",
                "evidence_nodes": ["need-recorded-eval"],
            },
        },
    ],
}

POST_BRIEF_UNANIMITY = {
    "id": "legitimate-post-brief-unanimity",
    "title": "Unanimous YES after independent briefs and evidence",
    "question": QUESTION,
    "expected_trigger": False,
    "class": "legitimate-unanimity",
    "participants": [
        {
            "id": "analyst",
            "role": "analyst",
            "vote": "YES",
            "brief": {
                "text": "Integer addition: 1+1 binds to 2; == is identity on ints.",
                "evidence_nodes": ["peps/pep-0237-int-unify"],
            },
        },
        {
            "id": "experimentalist",
            "role": "experimentalist",
            "vote": "YES",
            "brief": {
                "text": "eval('(1+1)==2') returned True in this process.",
                "evidence_nodes": ["live-eval:(1+1)==2"],
            },
        },
        {
            "id": "language-lawyer",
            "role": "language-lawyer",
            "vote": "YES",
            "brief": {
                "text": "The comparison dunder on int is value equality; 2==2.",
                "evidence_nodes": ["cpython/Objects/longobject.c:long_compare"],
            },
        },
        {
            "id": "scribe",
            "role": "scribe",
            "vote": "YES",
            "brief": {
                "text": "Four independent evidence nodes, one shared conclusion.",
                "evidence_nodes": ["minutes/round-1-independent-briefs"],
            },
        },
    ],
}

ALL_FIXTURES = (INSTANT_UNANIMITY, CONTESTED, POST_BRIEF_UNANIMITY)


def by_id(fid: str) -> dict:
    for row in ALL_FIXTURES:
        if row["id"] == fid:
            return row
    raise KeyError(fid)
