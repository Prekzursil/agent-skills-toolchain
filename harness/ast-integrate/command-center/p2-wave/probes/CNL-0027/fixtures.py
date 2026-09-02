#!/usr/bin/env python3
"""Triad round fixtures for CNL-0027.

known_good: proposer files P1, critic files O1 targeting P1, synthesiser
selects P1 and addresses O1. Mention of a hypothetical option in prose.
planted_new_proposal: synthesiser injects P-SYNTH (second proposer).
planted_new_objection: synthesiser injects O-SYNTH (third critic).
mention_only: prose names P-HYPOTHETICAL but typed fields stay closed-world.
critic_proposes: critic files a new option_id (critic-as-proposer).
coverage_plus_mint: cites every filed id AND mints — coverage=1, still FIRE.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

_BASE_PROPOSALS = [
    {
        "option_id": "P1",
        "author_seat": "proposer-a",
        "claim": "Adopt typed closed-world citation as the triad gate.",
        "evidence_cites": ["catalog:CNL-0027"],
    },
    {
        "option_id": "P2",
        "author_seat": "proposer-b",
        "claim": "Keep role separation as prompt text only.",
        "evidence_cites": ["prompt:role-label"],
    },
]
_BASE_CRITIQUES = [
    {
        "objection_id": "O1",
        "author_seat": "critic-a",
        "targets": "P2",
        "claim": "Prompt labels are not a gate: a synthesiser can mint a new option.",
    },
    {
        "objection_id": "O2",
        "author_seat": "critic-b",
        "targets": "P1",
        "claim": "Closed-world citation still misses prose-only smuggle.",
    },
]


def _round(
    round_id: str,
    synthesis: dict[str, Any],
    critiques: list[dict[str, Any]] | None = None,
    proposals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "round_id": round_id,
        "proposals": deepcopy(proposals if proposals is not None else _BASE_PROPOSALS),
        "critiques": deepcopy(critiques if critiques is not None else _BASE_CRITIQUES),
        "synthesis": deepcopy(synthesis),
    }


def known_good() -> dict[str, Any]:
    return _round(
        "known-good",
        {
            "author_seat": "synthesiser-a",
            "selects": ["P1"],
            "addresses": ["O1"],
            "unresolved": ["O2"],
            "ranked_options": [{"option_id": "P1", "rank": 1}, {"option_id": "P2", "rank": 2}],
            "notes": (
                "Selecting P1. Mention only: a hypothetical P-HYPOTHETICAL is "
                "not filed and is not selected. O1 is addressed; O2 stays unresolved."
            ),
        },
    )


def planted_new_proposal() -> dict[str, Any]:
    return _round(
        "planted-new-proposal",
        {
            "author_seat": "synthesiser-a",
            "selects": ["P1", "P-SYNTH"],
            "addresses": ["O1", "O2"],
            "unresolved": [],
            "new_proposal": {
                "option_id": "P-SYNTH",
                "claim": "A third option the proposers never filed.",
            },
            "notes": "Injecting P-SYNTH as if synthesis were a second proposer.",
        },
    )


def planted_new_objection() -> dict[str, Any]:
    return _round(
        "planted-new-objection",
        {
            "author_seat": "synthesiser-a",
            "selects": ["P1"],
            "addresses": ["O1", "O2", "O-SYNTH"],
            "unresolved": [],
            "new_objection": {
                "objection_id": "O-SYNTH",
                "claim": "A new critique the critics never filed.",
            },
            "notes": "Injecting O-SYNTH as if synthesis were a third critic.",
        },
    )


def mention_only() -> dict[str, Any]:
    """Use-vs-mention: prose names a new option; typed fields do not mint it."""
    return _round(
        "mention-only",
        {
            "author_seat": "synthesiser-a",
            "selects": ["P1"],
            "addresses": ["O1"],
            "unresolved": ["O2"],
            "notes": (
                "The critic asked whether we should propose P-HYPOTHETICAL. "
                "We mention that name and do not file or select it."
            ),
        },
    )


def critic_proposes() -> dict[str, Any]:
    critiques = deepcopy(_BASE_CRITIQUES)
    critiques[0]["option_id"] = "P-CRITIC"
    critiques[0]["new_proposal"] = {
        "option_id": "P-CRITIC",
        "claim": "Critic mints a competing option.",
    }
    return _round(
        "critic-proposes",
        {
            "author_seat": "synthesiser-a",
            "selects": ["P1"],
            "addresses": ["O1"],
            "unresolved": ["O2"],
            "notes": "Synthesis stays closed-world; the critic drifted.",
        },
        critiques=critiques,
    )


def coverage_plus_mint() -> dict[str, Any]:
    """Cites every filed id (coverage 1.0) and still mints. Coverage alone is insufficient."""
    return _round(
        "coverage-plus-mint",
        {
            "author_seat": "synthesiser-a",
            "selects": ["P1", "P2", "P-COVER"],
            "addresses": ["O1", "O2"],
            "unresolved": [],
            "ranked_options": [
                {"option_id": "P1", "rank": 1},
                {"option_id": "P2", "rank": 2},
            ],
            "new_proposal": {
                "option_id": "P-COVER",
                "claim": "Minted while citing the whole filed set.",
            },
        },
    )


ALL_FIXTURES = {
    "known_good": known_good,
    "planted_new_proposal": planted_new_proposal,
    "planted_new_objection": planted_new_objection,
    "mention_only": mention_only,
    "critic_proposes": critic_proposes,
    "coverage_plus_mint": coverage_plus_mint,
}
