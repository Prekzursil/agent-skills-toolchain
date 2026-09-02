#!/usr/bin/env python3
"""Freeze-set majority/supermajority tally and shrinking-denominator detector.

Denominator is the freeze-set locked at vote-open. Abstention, death, and
unreplaced seats do not shrink it. Quorum is a separate participating-seat
floor: failing it voids the vote rather than lowering the bar.
"""
from __future__ import annotations

from typing import Any

YES = "yes"
NO = "no"
ABSTAIN = "abstain"
ABSENT = "absent"
SUBMITTED = frozenset({YES, NO, ABSTAIN})
PRESENT_AND_VOTING = frozenset({YES, NO})

MAJORITY = {"kind": "majority"}
SUPERMAJORITY_2_3 = {
    "kind": "supermajority",
    "numerator": 2,
    "denominator": 3,
}


def freeze_n(profile: dict[str, Any]) -> int:
    # FREEZE-N: len(freeze_set) locked at vote-open; replacement substitutes a slot
    seats = profile["freeze_set"]
    if len(seats) != len(set(seats)):
        raise ValueError("freeze_set contains duplicate seats")
    return len(seats)


def choice_by_seat(profile: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    freeze = set(profile["freeze_set"])
    for row in profile["ballots"]:
        seat = row["seat"]
        if seat not in freeze:
            raise ValueError(f"ballot seat {seat!r} not in freeze_set")
        if seat in out:
            raise ValueError(f"duplicate ballot for {seat!r}")
        choice = row["choice"]
        if choice not in {YES, NO, ABSTAIN, ABSENT}:
            raise ValueError(f"unknown choice {choice!r}")
        out[seat] = choice
    for seat in profile["freeze_set"]:
        out.setdefault(seat, ABSENT)
    return out


def count_choice(profile: dict[str, Any], wanted: str) -> int:
    by = choice_by_seat(profile)
    return sum(1 for seat in profile["freeze_set"] if by[seat] == wanted)


def yes_count(profile: dict[str, Any]) -> int:
    return count_choice(profile, YES)


def participating_n(profile: dict[str, Any]) -> int:
    """Seats that submitted yes/no/abstain. Dead/absent do not count."""
    by = choice_by_seat(profile)
    return sum(1 for seat in profile["freeze_set"] if by[seat] in SUBMITTED)


def shrunk_n(profile: dict[str, Any]) -> int:
    """Gameable present-and-voting denominator (excludes abstain and absent)."""
    by = choice_by_seat(profile)
    return sum(1 for seat in profile["freeze_set"] if by[seat] in PRESENT_AND_VOTING)


def threshold_met(yes: int, n: int, rule: dict[str, Any]) -> bool:
    if n <= 0:
        return False
    kind = rule["kind"]
    if kind == "majority":
        # MAJORITY: 2 * yes > n (strict more than half of the stated denominator)
        return 2 * yes > n
    if kind == "supermajority":
        k = int(rule["numerator"])
        m = int(rule["denominator"])
        if k <= 0 or m <= 0 or k >= m:
            raise ValueError("supermajority k/m must satisfy 0 < k < m")
        # SUPERMAJORITY: m * yes >= k * n  (default 2/3 => 3*yes >= 2*n)
        return m * yes >= k * n
    raise ValueError(f"unknown rule kind {kind!r}")


def quorum_met(profile: dict[str, Any]) -> bool:
    q = int(profile["quorum"])
    if q < 1:
        raise ValueError("quorum must be >= 1")
    return participating_n(profile) >= q


def shrinking_fires(frozen_pass: bool, shrunk_pass: bool) -> bool:
    # DETECTOR: FIRE iff same yes-count fails freeze-N but passes shrunk N
    return bool(shrunk_pass) and not bool(frozen_pass)


def decide(profile: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    n = freeze_n(profile)
    yes = yes_count(profile)
    no = count_choice(profile, NO)
    abstain = count_choice(profile, ABSTAIN)
    absent = count_choice(profile, ABSENT)
    n_part = participating_n(profile)
    n_shrunk = shrunk_n(profile)
    frozen_pass = threshold_met(yes, n, rule)
    shrunk_pass = threshold_met(yes, n_shrunk, rule)
    fires = shrinking_fires(frozen_pass, shrunk_pass)
    q_ok = quorum_met(profile)
    if not q_ok:
        outcome = "NO_QUORUM"
    elif frozen_pass:
        outcome = "PASS"
    else:
        outcome = "FAIL"
    return {
        "fixture_id": profile.get("id"),
        "rule": rule,
        "freeze_n": n,
        "yes": yes,
        "no": no,
        "abstain": abstain,
        "absent": absent,
        "participating_n": n_part,
        "shrunk_n": n_shrunk,
        "quorum": int(profile["quorum"]),
        "quorum_met": q_ok,
        "frozen_pass": frozen_pass,
        "shrunk_pass": shrunk_pass,
        "detector": "FIRE" if fires else "SILENT",
        "outcome": outcome,
    }


def replace_seat(
    profile: dict[str, Any], old: str, new: str, choice: str
) -> dict[str, Any]:
    """Mid-council replacement: substitute a freeze-set slot. N does not drop."""
    if old not in profile["freeze_set"]:
        raise ValueError(f"cannot replace unknown seat {old!r}")
    if new in profile["freeze_set"] and new != old:
        raise ValueError(f"replacement {new!r} already in freeze_set")
    freeze = [new if s == old else s for s in profile["freeze_set"]]
    ballots = [dict(b) for b in profile["ballots"] if b["seat"] != old]
    ballots.append({"seat": new, "choice": choice, "replaces": old})
    out = dict(profile)
    out["freeze_set"] = freeze
    out["ballots"] = ballots
    out["replaced"] = {"from": old, "to": new}
    return out


def compact(row: dict[str, Any]) -> str:
    keys = (
        "fixture_id",
        "freeze_n",
        "yes",
        "shrunk_n",
        "frozen_pass",
        "shrunk_pass",
        "detector",
        "quorum_met",
        "outcome",
    )
    return " ".join(f"{k}={row[k]!s}" for k in keys)
