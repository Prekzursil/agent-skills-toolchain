#!/usr/bin/env python3
"""Worked IRV fixtures for CNL-0061. Roster sizes 7 (inside 3-15)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


# 7-seat council, 3 options. Last-place tie in round 1. Raising winner C on
# one ballot (A>C>B -> C>A>B) flips the winner to B under lex-min elim.
NM7X3_OPTIONS = ["A", "B", "C"]
NM7X3_ORIGINAL_RANKS = [
    ["A", "B", "C"],
    ["A", "B", "C"],
    ["A", "C", "B"],
    ["B", "C", "A"],
    ["B", "C", "A"],
    ["C", "B", "A"],
    ["C", "B", "A"],
]
NM7X3_RAISE_INDEX = 2
NM7X3_RAISED_CANDIDATE = "C"
NM7X3_RAISED_RANKS = [
    ["A", "B", "C"],
    ["A", "B", "C"],
    ["C", "A", "B"],
    ["B", "C", "A"],
    ["B", "C", "A"],
    ["C", "B", "A"],
    ["C", "B", "A"],
]

# Majority negative control: A already has 4/7 > 3.5. Raising A cannot unseat A.
MAJORITY7_OPTIONS = ["A", "B", "C"]
MAJORITY7_ORIGINAL_RANKS = [
    ["A", "B", "C"],
    ["A", "B", "C"],
    ["A", "B", "C"],
    ["A", "B", "C"],
    ["B", "A", "C"],
    ["B", "A", "C"],
    ["C", "B", "A"],
]
MAJORITY7_RAISED_RANKS = [
    ["A", "B", "C"],
    ["A", "B", "C"],
    ["A", "B", "C"],
    ["A", "B", "C"],
    ["A", "B", "C"],
    ["B", "A", "C"],
    ["C", "B", "A"],
]

# 7-seat, 4 options. Round-1 last place is unique (C has 0). Raising D on the
# A>B>D>C ballot still flips D -> B, so the pathology is not only a round-1 tie.
NM7X4_OPTIONS = ["A", "B", "C", "D"]
NM7X4_ORIGINAL_RANKS = [
    ["A", "B", "C", "D"],
    ["A", "B", "C", "D"],
    ["B", "D", "A", "C"],
    ["A", "B", "D", "C"],
    ["B", "C", "D", "A"],
    ["D", "C", "B", "A"],
    ["D", "A", "C", "B"],
]
NM7X4_RAISED_RANKS = [
    ["A", "B", "C", "D"],
    ["A", "B", "C", "D"],
    ["B", "D", "A", "C"],
    ["D", "A", "B", "C"],
    ["B", "C", "D", "A"],
    ["D", "C", "B", "A"],
    ["D", "A", "C", "B"],
]
NM7X4_RAISED_CANDIDATE = "D"

# Later-no-harm: truncated first-choice A is winning; completing later ranks
# must not unseat A under IRV.
LNH_OPTIONS = ["A", "B", "C"]
LNH_TRUNCATED_RANKS = [["A"], ["A"], ["A"], ["B", "A"], ["B", "A"]]
LNH_COMPLETED_RANKS = [["A", "B", "C"], ["A"], ["A"], ["B", "A"], ["B", "A"]]
LNH_FIRST_CHOICE = "A"

# Vacuity bait for the LNH detector (NOT a council method): second-place
# plurality. Completing A -> A>B elects B, harming first-choice A.
BAIT_TRUNCATED_RANKS = [["A"], ["A"], ["A"], ["B"], ["B"]]
BAIT_COMPLETED_RANKS = [["A", "B"], ["A"], ["A"], ["B"], ["B"]]
BAIT_OPTIONS = ["A", "B", "C"]
BAIT_FIRST_CHOICE = "A"

# Weighted copy of NM-7x3: doubling one C>B>A ballot must match two unit ballots.
WEIGHTED_OPTIONS = ["A", "B", "C"]
WEIGHTED_BALLOTS: list[tuple[list[str], float]] = [
    (["A", "B", "C"], 1.0),
    (["A", "B", "C"], 1.0),
    (["A", "C", "B"], 1.0),
    (["B", "C", "A"], 1.0),
    (["B", "C", "A"], 1.0),
    (["C", "B", "A"], 2.0),
]


def pack(options: list[str], ranks: list[list[str]]) -> dict:
    return {
        "options": list(options),
        "ballots": [{"ranks": list(r), "weight": 1.0} for r in ranks],
        "roster_size": len(ranks),
    }


def as_ballots(doc: dict) -> list[tuple[list[str], float]]:
    out: list[tuple[list[str], float]] = []
    for row in doc["ballots"]:
        out.append((list(row["ranks"]), float(row["weight"])))
    return out


def named() -> dict[str, dict]:
    return {
        "nm-7x3-original": {
            **pack(NM7X3_OPTIONS, NM7X3_ORIGINAL_RANKS),
            "raised_candidate": NM7X3_RAISED_CANDIDATE,
            "role": "nonmonotonicity-original",
        },
        "nm-7x3-raised": {
            **pack(NM7X3_OPTIONS, NM7X3_RAISED_RANKS),
            "raised_candidate": NM7X3_RAISED_CANDIDATE,
            "role": "nonmonotonicity-raised",
        },
        "majority-7-original": {
            **pack(MAJORITY7_OPTIONS, MAJORITY7_ORIGINAL_RANKS),
            "raised_candidate": "A",
            "role": "majority-negative-original",
        },
        "majority-7-raised": {
            **pack(MAJORITY7_OPTIONS, MAJORITY7_RAISED_RANKS),
            "raised_candidate": "A",
            "role": "majority-negative-raised",
        },
        "nm-7x4-original": {
            **pack(NM7X4_OPTIONS, NM7X4_ORIGINAL_RANKS),
            "raised_candidate": NM7X4_RAISED_CANDIDATE,
            "role": "nonmonotonicity-4opt-original",
        },
        "nm-7x4-raised": {
            **pack(NM7X4_OPTIONS, NM7X4_RAISED_RANKS),
            "raised_candidate": NM7X4_RAISED_CANDIDATE,
            "role": "nonmonotonicity-4opt-raised",
        },
        "lnh-irv-truncated": {
            **pack(LNH_OPTIONS, LNH_TRUNCATED_RANKS),
            "first_choice": LNH_FIRST_CHOICE,
            "role": "later-no-harm-irv-before",
        },
        "lnh-irv-completed": {
            **pack(LNH_OPTIONS, LNH_COMPLETED_RANKS),
            "first_choice": LNH_FIRST_CHOICE,
            "role": "later-no-harm-irv-after",
        },
        "lnh-bait-truncated": {
            **pack(BAIT_OPTIONS, BAIT_TRUNCATED_RANKS),
            "first_choice": BAIT_FIRST_CHOICE,
            "role": "later-no-harm-bait-before",
        },
        "lnh-bait-completed": {
            **pack(BAIT_OPTIONS, BAIT_COMPLETED_RANKS),
            "first_choice": BAIT_FIRST_CHOICE,
            "role": "later-no-harm-bait-after",
        },
        "weighted-double-c": {
            "options": list(WEIGHTED_OPTIONS),
            "ballots": [
                {"ranks": list(r), "weight": w} for r, w in WEIGHTED_BALLOTS
            ],
            "roster_size": 6,
            "role": "weighted-equivalent-to-seven-unit-ballots",
        },
    }


def write_fixture_files() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    for name, doc in named().items():
        path = FIX / f"{name}.json"
        path.write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def load_named(name: str) -> dict:
    path = FIX / f"{name}.json"
    if not path.is_file():
        write_fixture_files()
    return json.loads(path.read_text(encoding="utf-8"))
