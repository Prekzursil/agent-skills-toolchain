"""Labelled imported-workflow candidate set for IMP-0165.

IMP-0164's receipt is not on this worktree. These documents are the IR
shape typed stage extraction would emit (id + stages/participants). Labels
live here; mapping lives in tools/workflow_foundry/role_extract.py.
"""
from __future__ import annotations

from typing import Any

UNKNOWN = "UNKNOWN"

# Each row: id, workflow document, expected canonical list in extraction order.
CANDIDATES: list[dict[str, Any]] = [
    {
        "id": "wf-comparable-critic-family",
        "expected": ["critic", "critic", "critic"],
        "workflow": {
            "id": "wf-comparable-critic-family",
            "participants": [
                {"id": "p-critic", "role": "critic"},
                {"id": "p-red", "role": "red team"},
                {"id": "p-refute", "role": "refuter"},
            ],
        },
    },
    {
        "id": "wf-case-and-punct",
        "expected": ["critic", "critic", "critic"],
        "workflow": {
            "id": "wf-case-and-punct",
            "agents": [
                {"id": "a1", "role": "Critic"},
                {"id": "a2", "role": "RED-TEAM"},
                {"id": "a3", "role": "Refuter!"},
            ],
        },
    },
    {
        "id": "wf-other-canonical",
        "expected": [
            "proposer",
            "chair",
            "voter",
            "observer",
            "implementer",
            "reviewer",
        ],
        "workflow": {
            "id": "wf-other-canonical",
            "seats": [
                {"id": "s-prop", "role": "author"},
                {"id": "s-chair", "role": "moderator"},
                {"id": "s-vote", "role": "judge"},
                {"id": "s-obs", "role": "scribe"},
                {"id": "s-imp", "role": "builder"},
                {"id": "s-rev", "role": "peer reviewer"},
            ],
        },
    },
    {
        "id": "wf-invented",
        "expected": [UNKNOWN, UNKNOWN, UNKNOWN],
        "workflow": {
            "id": "wf-invented",
            "participants": [
                {"id": "i1", "role": "floor-wax-auditor"},
                {"id": "i2", "role": "banana-steward"},
                {"id": "i3", "role": "quantum-shepherd"},
            ],
        },
    },
    {
        "id": "wf-near-miss-spellings",
        "expected": [UNKNOWN, UNKNOWN, UNKNOWN],
        "workflow": {
            "id": "wf-near-miss-spellings",
            "participants": [
                {"id": "n1", "role": "critc"},
                {"id": "n2", "role": "refutr"},
                {"id": "n3", "role": "red teem"},
            ],
        },
    },
    {
        "id": "wf-substring-traps",
        "expected": [UNKNOWN, UNKNOWN, UNKNOWN],
        "workflow": {
            "id": "wf-substring-traps",
            "participants": [
                {"id": "t1", "role": "critical-path-owner"},
                {"id": "t2", "role": "red teammate"},
                {"id": "t3", "role": "referee-adjacent"},
            ],
        },
    },
    {
        "id": "wf-nested-stages",
        "expected": ["critic", "proposer", UNKNOWN],
        "workflow": {
            "id": "wf-nested-stages",
            "stages": [
                {
                    "id": "stage-review",
                    "type": "review",
                    "participants": [
                        {"id": "st-c", "role": "devil's advocate"},
                        {"id": "st-p", "role": "architect"},
                        {"id": "st-x", "role": "mystery-role"},
                    ],
                }
            ],
        },
    },
    {
        "id": "wf-empty",
        "expected": [],
        "workflow": {"id": "wf-empty"},
    },
    {
        "id": "wf-blank-roles",
        "expected": [UNKNOWN, UNKNOWN],
        "workflow": {
            "id": "wf-blank-roles",
            "participants": [
                {"id": "b1", "role": ""},
                {"id": "b2", "role": None},
            ],
        },
    },
    {
        "id": "wf-extra-synonyms",
        "expected": ["critic", "critic", "critic", "critic"],
        "workflow": {
            "id": "wf-extra-synonyms",
            "crew": [
                {"id": "e1", "role": "skeptic"},
                {"id": "e2", "role": "challenger"},
                {"id": "e3", "role": "redteam"},
                {"id": "e4", "role": "adversarial-refuter"},
            ],
        },
    },
]


def labelled_stats() -> dict[str, Any]:
    total = 0
    unknown = 0
    for cand in CANDIDATES:
        for exp in cand["expected"]:
            total += 1
            if exp == UNKNOWN:
                unknown += 1
    rate = (unknown / total) if total else 0.0
    return {
        "total": total,
        "unknown": unknown,
        "known": total - unknown,
        "rate": rate,
        "candidate_count": len(CANDIDATES),
    }
