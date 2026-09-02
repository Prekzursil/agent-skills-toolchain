"""Cold-start, mixed-history, and planted-average fixtures for CNL-0014."""
from __future__ import annotations

from typing import Any

import store as S

TASK = "security-review"

COLD_CANDIDATES = [
    {"participant_id": "alice", "task_class": TASK},
    {"participant_id": "bob", "task_class": TASK},
    {"participant_id": "cara", "task_class": TASK},
    {"participant_id": "drew", "task_class": TASK},
]

ALICE_OUTCOMES = [
    {
        "council_id": "c-a1",
        "stated_confidence": 0.8,
        "resolution": "SCOREABLE",
        "resolved_correct": True,
        "resolution_source": "owner-settled:ticket-101",
    },
    {
        "council_id": "c-a2",
        "stated_confidence": 0.7,
        "resolution": "SCOREABLE",
        "resolved_correct": True,
        "resolution_source": "owner-settled:ticket-102",
    },
    {
        "council_id": "c-a3",
        "stated_confidence": 0.2,
        "resolution": "SCOREABLE",
        "resolved_correct": False,
        "resolution_source": "owner-settled:ticket-103",
    },
]

BOB_OUTCOMES = [
    {
        "council_id": "c-b1",
        "stated_confidence": 0.9,
        "resolution": "SCOREABLE",
        "resolved_correct": False,
        "resolution_source": "owner-settled:ticket-201",
    },
    {
        "council_id": "c-b2",
        "stated_confidence": 0.9,
        "resolution": "SCOREABLE",
        "resolved_correct": True,
        "resolution_source": "owner-settled:ticket-202",
    },
    {
        "council_id": "c-b3",
        "stated_confidence": 0.85,
        "resolution": "SCOREABLE",
        "resolved_correct": False,
        "resolution_source": "owner-settled:ticket-203",
    },
]

# Unresolved council: must not mint a score (CNL-0074 UNSCOREABLE path).
CARA_UNSCOREABLE = {
    "council_id": "c-u1",
    "stated_confidence": 0.99,
    "resolution": "UNSCOREABLE",
    "resolved_correct": None,
    "resolution_source": None,
}


def cold_start_store() -> dict[str, Any]:
    st = S.empty_store(min_resolved_n=1)
    for cand in COLD_CANDIDATES:
        S.observe_candidate(st, cand["participant_id"], cand["task_class"])
    return st


def mixed_store() -> dict[str, Any]:
    st = S.empty_store(min_resolved_n=1)
    for cand in COLD_CANDIDATES:
        S.observe_candidate(st, cand["participant_id"], cand["task_class"])
    for o in ALICE_OUTCOMES:
        S.append_outcome(st, "alice", TASK, o)
    for o in BOB_OUTCOMES:
        S.append_outcome(st, "bob", TASK, o)
    S.append_outcome(st, "cara", TASK, CARA_UNSCOREABLE)
    return st
