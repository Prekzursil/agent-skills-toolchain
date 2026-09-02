"""Planted fixtures for CNL-0021. Shared data, not shared conclusions."""
from __future__ import annotations

import copy

from runtime import Council, Seat

ARCH = Seat("seat-architect", "architect", "anthropic", "claude-opus-4")
SKEP = Seat("seat-skeptic", "skeptic", "anthropic", "claude-sonnet-4")
CRIT = Seat("seat-critic", "critic", "openai", "gpt-4o")
REPL = Seat("seat-architect-r2", "architect", "anthropic", "claude-opus-4")


def _base_council(**kwargs) -> Council:
    seats = [copy.deepcopy(ARCH), copy.deepcopy(SKEP), copy.deepcopy(CRIT)]
    return Council(seats=seats, quorum=2, target_rounds=2, **kwargs)


def midround_death_honest() -> tuple[Council, list[dict]]:
    """A dies mid-round 2 after casting in round 1. Replacement is a new seat_id."""
    c = _base_council()
    script = [
        {"kind": "idea", "idea_id": "I1", "seat_id": "seat-architect", "text": "ship lattice"},
        {"kind": "ballot", "seat_id": "seat-architect", "option": "A"},
        {"kind": "ballot", "seat_id": "seat-skeptic", "option": "B"},
        {"kind": "ballot", "seat_id": "seat-critic", "option": "A"},
        {"kind": "end-round"},
        {"kind": "death", "seat_id": "seat-architect", "reason": "crash", "replacement": copy.deepcopy(REPL)},
        {"kind": "ballot", "seat_id": "seat-skeptic", "option": "B"},
        {"kind": "ballot", "seat_id": "seat-critic", "option": "A"},
        {"kind": "ballot", "seat_id": "seat-architect-r2", "option": "A"},
        {"kind": "end-round"},
    ]
    return c, script


def midround_death_inherit_mutant() -> tuple[Council, list[dict]]:
    c, script = midround_death_honest()
    c.inherit_votes = True
    return c, script


def midround_death_reuse_id_mutant() -> tuple[Council, list[dict]]:
    c, script = midround_death_honest()
    c.reuse_seat_id = True
    for ev in script:
        if ev.get("kind") == "ballot" and ev.get("seat_id") == "seat-architect-r2":
            ev["seat_id"] = "seat-architect"
    return c, script


def midround_death_hang_mutant() -> tuple[Council, list[dict]]:
    c, script = midround_death_honest()
    c.hang_on_death = True
    return c, script


def midround_death_no_replacement_quorum_ok() -> tuple[Council, list[dict]]:
    c = _base_council()
    script = [
        {"kind": "ballot", "seat_id": "seat-architect", "option": "A"},
        {"kind": "ballot", "seat_id": "seat-skeptic", "option": "B"},
        {"kind": "ballot", "seat_id": "seat-critic", "option": "A"},
        {"kind": "end-round"},
        {"kind": "death", "seat_id": "seat-architect", "reason": "recusal", "replacement": None},
        {"kind": "ballot", "seat_id": "seat-skeptic", "option": "B"},
        {"kind": "ballot", "seat_id": "seat-critic", "option": "A"},
        {"kind": "end-round"},
    ]
    return c, script


def midround_death_no_replacement_quorum_fail() -> tuple[Council, list[dict]]:
    c = _base_council()
    c.quorum = 3
    script = [
        {"kind": "ballot", "seat_id": "seat-architect", "option": "A"},
        {"kind": "ballot", "seat_id": "seat-skeptic", "option": "B"},
        {"kind": "ballot", "seat_id": "seat-critic", "option": "A"},
        {"kind": "end-round"},
        {"kind": "death", "seat_id": "seat-architect", "reason": "quota", "replacement": None},
    ]
    return c, script


def roster_same_base_model_different_roles() -> list[Seat]:
    """Planted reject state: same base model, nominally different seats."""
    return [
        Seat("s-arch", "architect", "anthropic", "claude-opus-4", declared_independent=True),
        Seat(
            "s-skep",
            "skeptic",
            "anthropic",
            "claude-opus-4-20250514",
            declared_independent=True,
        ),
    ]


def roster_genuinely_different() -> list[Seat]:
    return [
        Seat("s-arch", "architect", "anthropic", "claude-opus-4"),
        Seat("s-skep", "skeptic", "openai", "gpt-4o"),
    ]


def roster_gpt4o_vs_gpt41() -> list[Seat]:
    return [
        Seat("s-a", "architect", "openai", "gpt-4o"),
        Seat("s-b", "skeptic", "openai", "gpt-4.1"),
    ]


def roster_cross_vendor_same_model() -> list[Seat]:
    return [
        Seat("s-oa", "architect", "openai", "gpt-4o"),
        Seat("s-az", "skeptic", "azure-openai", "openai/gpt-4o"),
    ]


def roster_three_with_one_duplicate() -> list[Seat]:
    return [
        Seat("s-arch", "architect", "anthropic", "claude-opus-4"),
        Seat("s-skep", "skeptic", "anthropic", "claude-opus-4-20250514"),
        Seat("s-crit", "critic", "openai", "gpt-4o"),
    ]


def roster_unattested() -> list[Seat]:
    return [
        Seat("s-arch", "architect", "anthropic", "claude-opus-4"),
        Seat("s-ghost", "observer", "unknown", ""),
    ]
