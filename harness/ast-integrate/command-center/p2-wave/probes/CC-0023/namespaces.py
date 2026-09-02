"""Four M-NN namespaces that share the prefix on this estate.

Card sets are the catalogued sizes: option-universe family M = 33,
architecture-candidate mechanisms = 38 (re-prefixed MECH-NN on 2026-08-07),
wave3 deep-research Research Harness = {16}, wave1 register = {1, 3}.
Intersection of option and mechanism numbers is 31 (the historical collision).
"""
from __future__ import annotations

from typing import Any

# Option universe family M: 33 cards, numbers 1-33.
OPTION_IDS = list(range(1, 34))

# Architecture mechanisms: 38 cards. Numbers 1-31 plus 34-40 so the
# option∩mech collision is exactly 31, matching the logged 31-way case.
MECH_IDS = list(range(1, 32)) + list(range(34, 41))

WAVE3_IDS = [16]
WAVE1_IDS = [1, 3]

NAMESPACES: list[dict[str, Any]] = [
    {
        "id": "option-universe",
        "prefix": "M",
        "title": "07-OPTION-UNIVERSE family M",
        "ids": OPTION_IDS,
        "card_count": 33,
    },
    {
        "id": "architecture-mech",
        "prefix": "MECH",
        "title": "13-ARCHITECTURE-CANDIDATES mechanisms (MECH-NN since 2026-08-07)",
        "ids": MECH_IDS,
        "card_count": 38,
    },
    {
        "id": "wave3-deep-research",
        "prefix": "M",
        "title": "wave3 deep-research SKILL.md Research Harness (M-16)",
        "ids": WAVE3_IDS,
        "card_count": 1,
    },
    {
        "id": "wave1-register",
        "prefix": "M",
        "title": "wave1/REGISTER.md mission-grade M-1/M-3",
        "ids": WAVE1_IDS,
        "card_count": 2,
    },
]


def holders(token_number: int) -> list[str]:
    return [ns["id"] for ns in NAMESPACES if token_number in ns["ids"]]


def collision_numbers() -> list[int]:
    opt = set(OPTION_IDS)
    mech = set(MECH_IDS)
    return sorted(opt & mech)
