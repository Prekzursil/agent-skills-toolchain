#!/usr/bin/env python3
"""Deterministic long-council fixture for IMP-0348 compaction probes."""
from __future__ import annotations

from typing import Any

COUNCIL_ID = "council-imp-0348-long-fixture"

# Canonical load-bearing records. Statements stay short; turn prose is padding.
CLAIMS = [
    {
        "id": "C-001",
        "kind": "claim",
        "statement": "Adopt the hashed event log as the sole council state.",
        "author": "seat-proposer",
        "round": 1,
        "mechanism": "append-only-log",
    },
    {
        "id": "C-002",
        "kind": "claim",
        "statement": "Seat a dedicated refuter against each proposer.",
        "author": "seat-critic",
        "round": 1,
        "mechanism": "adversarial-pairing",
    },
    {
        "id": "C-003",
        "kind": "claim",
        "statement": "Require a freshness stamp on every evidence anchor.",
        "author": "seat-auditor",
        "round": 2,
        "mechanism": "anchor-freshness",
    },
    {
        "id": "C-004",
        "kind": "claim",
        "statement": "Allow silent substitution of an unavailable named seat.",
        "author": "seat-operator",
        "round": 2,
        "mechanism": "silent-substitute",
    },
    {
        "id": "C-005",
        "kind": "claim",
        "statement": "Preserve every dissent by id through synthesis.",
        "author": "seat-scribe",
        "round": 3,
        "mechanism": "dissent-conservation",
    },
    {
        "id": "C-006",
        "kind": "claim",
        "statement": "Compact long transcripts by dropping unread ids.",
        "author": "seat-operator",
        "round": 3,
        "mechanism": "lossy-compact",
    },
    {
        "id": "C-007",
        "kind": "claim",
        "statement": "Pin sampling seeds and record NOT-PINNABLE vendors.",
        "author": "seat-repro",
        "round": 4,
        "mechanism": "seed-pinning",
    },
    {
        "id": "C-008",
        "kind": "claim",
        "statement": "Treat identical vendor+model+prompt seats as one voice.",
        "author": "seat-integrity",
        "round": 4,
        "mechanism": "effective-independence",
    },
]

OBJECTIONS = [
    {
        "id": "O-001",
        "kind": "objection",
        "statement": "Silent substitution hides an empty seat in the tally.",
        "author": "seat-critic",
        "target_id": "C-004",
        "round": 2,
    },
    {
        "id": "O-002",
        "kind": "objection",
        "statement": "Dropping unread ids is claim-id loss, not compaction.",
        "author": "seat-auditor",
        "target_id": "C-006",
        "round": 3,
    },
    {
        "id": "O-003",
        "kind": "objection",
        "statement": "A freshness stamp that rereads cache is not revalidation.",
        "author": "seat-refuter",
        "target_id": "C-003",
        "round": 2,
    },
    {
        "id": "O-004",
        "kind": "objection",
        "statement": "Pairing without a private channel still leaks identity.",
        "author": "seat-integrity",
        "target_id": "C-002",
        "round": 1,
    },
    {
        "id": "O-005",
        "kind": "objection",
        "statement": "Log rebuild fails if any side state is consulted.",
        "author": "seat-repro",
        "target_id": "C-001",
        "round": 1,
    },
    {
        "id": "O-006",
        "kind": "objection",
        "statement": "Independence count of 1 must be reported, not papered over.",
        "author": "seat-auditor",
        "target_id": "C-008",
        "round": 4,
    },
]

DISSENTS = [
    {
        "id": "D-001",
        "kind": "dissent",
        "statement": "Minority: do not adopt C-004; empty seats must fail closed.",
        "author": "seat-critic",
        "round": 5,
    },
    {
        "id": "D-002",
        "kind": "dissent",
        "statement": "Minority: C-006 is a named failure class (dissent/id drop).",
        "author": "seat-scribe",
        "round": 5,
    },
    {
        "id": "D-003",
        "kind": "dissent",
        "statement": "Minority: seed pinning is NOT-PINNABLE on at least one vendor.",
        "author": "seat-repro",
        "round": 5,
    },
    {
        "id": "D-004",
        "kind": "dissent",
        "statement": "Minority: keep C-005 even if the majority summarises it away.",
        "author": "seat-auditor",
        "round": 5,
    },
]

EDGES = [
    {"id": "E-S-001", "rel": "SUPPORTS", "source": "C-005", "target": "C-001"},
    {"id": "E-S-002", "rel": "SUPPORTS", "source": "C-007", "target": "C-001"},
    {"id": "E-S-003", "rel": "SUPPORTS", "source": "C-008", "target": "C-002"},
    {"id": "E-A-001", "rel": "ATTACKS", "source": "O-001", "target": "C-004"},
    {"id": "E-A-002", "rel": "ATTACKS", "source": "O-002", "target": "C-006"},
    {"id": "E-R-001", "rel": "REBUTS", "source": "C-003", "target": "E-A-003"},
    {"id": "E-A-003", "rel": "ATTACKS", "source": "O-003", "target": "C-003"},
]

VOTES = [
    {"seat": "seat-proposer", "choice": "C-001", "weight": 1, "kind": "vote"},
    {"seat": "seat-critic", "choice": "C-005", "weight": 1, "kind": "vote"},
    {"seat": "seat-auditor", "choice": "C-001", "weight": 1, "kind": "vote"},
    {"seat": "seat-scribe", "choice": "C-005", "weight": 1, "kind": "vote"},
    {"seat": "seat-repro", "choice": "C-007", "weight": 1, "kind": "vote"},
    {"seat": "seat-integrity", "choice": "C-008", "weight": 1, "kind": "vote"},
    {"seat": "seat-refuter", "choice": "C-002", "weight": 1, "kind": "vote"},
    {"seat": "seat-operator", "choice": "C-004", "weight": 1, "kind": "vote"},
]

PADDING = (
    " Chamber notes, not load-bearing: the drapes were blue, the clock drifted, "
    "someone restated the agenda, someone restated it again, coffee cooled, "
    "and the scribe recorded filler that must not be required for id reachability. "
)


def _turn_prose(i: int, tagged: str) -> str:
    return (
        f"Turn {i:04d} opening.{PADDING * 8}"
        f" {tagged} "
        f"Turn {i:04d} closing.{PADDING * 4}"
    )


def build_long_transcript() -> dict[str, Any]:
    """Build a verbose transcript whose ids live in both registry and turn prose."""
    turns: list[dict[str, Any]] = []
    seats = [
        "seat-proposer",
        "seat-critic",
        "seat-auditor",
        "seat-scribe",
        "seat-repro",
        "seat-integrity",
        "seat-refuter",
        "seat-operator",
    ]
    tagged_cycle = (
        [f"[claim:{c['id']}] {c['statement']}" for c in CLAIMS]
        + [f"[objection:{o['id']} -> {o['target_id']}] {o['statement']}" for o in OBJECTIONS]
        + [f"[dissent:{d['id']}] {d['statement']}" for d in DISSENTS]
    )
    for i in range(72):
        seat = seats[i % len(seats)]
        tag = tagged_cycle[i % len(tagged_cycle)]
        turn: dict[str, Any] = {
            "turn_id": f"T-{i:04d}",
            "speaker": seat,
            "round": (i // 8) + 1,
            "text": _turn_prose(i, tag),
        }
        if i < len(CLAIMS):
            turn["claims"] = [CLAIMS[i]]
        if i < len(OBJECTIONS):
            turn["objections"] = [OBJECTIONS[i]]
        if i < len(DISSENTS):
            turn["dissents"] = [DISSENTS[i]]
        if i < len(VOTES):
            turn["vote"] = VOTES[i]
        turns.append(turn)

    # Top-level registry duplicates the same ids (set semantics, not double count).
    return {
        "council_id": COUNCIL_ID,
        "question": "Which council runtime claims survive compaction by id?",
        "turns": turns,
        "registry": {
            "claims": CLAIMS,
            "objections": OBJECTIONS,
            "dissents": DISSENTS,
        },
        "edges": EDGES,
        "votes": VOTES,
        "padding_note": PADDING * 20,
    }
