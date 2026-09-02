#!/usr/bin/env python3
"""Independent recount: integer tally from freeze_set + ballots, no tally.py import.

A disagreement with the author's tabulated numbers blocks the unit.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def recount(profile: dict[str, Any]) -> dict[str, Any]:
    seats = list(profile["freeze_set"])
    n = len(seats)
    if n != len(set(seats)):
        raise ValueError("duplicate freeze_set seats")
    by: dict[str, str] = {b["seat"]: b["choice"] for b in profile["ballots"]}
    if len(by) != len(profile["ballots"]):
        raise ValueError("duplicate ballot seats")
    yes = no = abstain = absent = 0
    for seat in seats:
        choice = by.get(seat, "absent")
        if choice == "yes":
            yes += 1
        elif choice == "no":
            no += 1
        elif choice == "abstain":
            abstain += 1
        elif choice == "absent":
            absent += 1
        else:
            raise ValueError(f"unknown choice {choice!r}")
    participating = yes + no + abstain
    shrunk = yes + no
    quorum = int(profile["quorum"])
    majority_frozen = 2 * yes > n
    majority_shrunk = 2 * yes > shrunk if shrunk > 0 else False
    super_frozen = 3 * yes >= 2 * n
    super_shrunk = 3 * yes >= 2 * shrunk if shrunk > 0 else False
    q_ok = participating >= quorum
    super_fires = super_shrunk and not super_frozen
    maj_fires = majority_shrunk and not majority_frozen
    if not q_ok:
        outcome = "NO_QUORUM"
    elif super_frozen:
        outcome = "PASS"
    else:
        outcome = "FAIL"
    return {
        "freeze_n": n,
        "yes": yes,
        "no": no,
        "abstain": abstain,
        "absent": absent,
        "participating_n": participating,
        "shrunk_n": shrunk,
        "quorum_met": q_ok,
        "majority_frozen_pass": majority_frozen,
        "majority_shrunk_pass": majority_shrunk,
        "super_frozen_pass": super_frozen,
        "super_shrunk_pass": super_shrunk,
        "detector": "FIRE" if super_fires else "SILENT",
        "majority_detector": "FIRE" if maj_fires else "SILENT",
        "outcome": outcome,
    }


def text_yes_count(raw: str) -> int:
    """Second mechanism: count yes-choice tokens in the fixture bytes, not JSON fields."""
    return len(re.findall(r'"choice"\s*:\s*"yes"', raw))


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
