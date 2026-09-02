#!/usr/bin/env python3
"""Independent IRV recount for CNL-0061.

Different mechanism from irv_author.py: each ballot is a mutable queue of
remaining ranks. A round pops from the left until the front is still standing
or the queue is empty. Tallies are rebuilt from queue fronts; the author
instead scans immutable rank lists. Same LOOKBACK-THEN-LEX-MIN-ELIM policy.
A disagreement in the winner number/id blocks the unit.
"""
from __future__ import annotations

from collections import deque
from typing import Any

POLICY = "lookback-then-lex-min-elim"


def recount(options: list[str], ballots: list[tuple[list[str], float]]) -> dict[str, Any]:
    standing = set(dict.fromkeys(options))
    queues = [(deque(ranks), float(weight)) for ranks, weight in ballots]
    past: list[dict[str, float]] = []
    rounds: list[dict[str, Any]] = []

    while standing:
        fronts: dict[str, float] = {c: 0.0 for c in standing}
        live = 0.0
        dead = 0.0
        next_queues: list[tuple[deque[str], float]] = []
        for q, w in queues:
            qq = deque(q)
            while qq and qq[0] not in standing:
                qq.popleft()
            if not qq:
                dead += w
                next_queues.append((qq, w))
                continue
            fronts[qq[0]] += w
            live += w
            next_queues.append((qq, w))
        queues = next_queues
        row: dict[str, Any] = {
            "standing": sorted(standing),
            "tally": {k: fronts[k] for k in sorted(fronts)},
            "continuing_weight": live,
            "exhausted_weight": dead,
        }
        if live <= 0.0:
            win = min(standing)
            row["winner"] = win
            row["exhausted_residual"] = True
            rounds.append(row)
            return {"winner": win, "how": "exhausted-residual", "rounds": rounds, "policy": POLICY}
        quota = live / 2.0
        row["quota"] = quota
        above = sorted(c for c, v in fronts.items() if v > quota)
        if len(above) == 1:
            row["winner"] = above[0]
            row["majority"] = True
            rounds.append(row)
            return {
                "winner": above[0],
                "how": "strict-majority-continuing",
                "rounds": rounds,
                "policy": POLICY,
            }
        if len(standing) == 1:
            win = next(iter(standing))
            row["winner"] = win
            rounds.append(row)
            return {"winner": win, "how": "last-remaining", "rounds": rounds, "policy": POLICY}
        floor = min(fronts.values())
        bottom = sorted(c for c, v in fronts.items() if v == floor)
        row["last_place"] = bottom
        row["min_tally"] = floor
        if set(bottom) == standing:
            win = min(standing)
            row["winner"] = win
            row["total_tie"] = True
            rounds.append(row)
            return {"winner": win, "how": "total-tie-lex-min", "rounds": rounds, "policy": POLICY}
        drop, rule = _break_bottom(bottom, past)
        row["eliminated"] = drop
        row["tie_break_used"] = len(bottom) > 1
        row["elim_rule"] = rule
        rounds.append(row)
        past.append(fronts)
        standing.remove(drop)
    raise RuntimeError("reviewer IRV emptied standing")


def _break_bottom(
    bottom: list[str], past: list[dict[str, float]]
) -> tuple[str, str]:
    pool = set(bottom)
    if len(pool) == 1:
        return next(iter(pool)), "unique-last"
    for older in past:
        slice_vals = {c: older[c] for c in pool if c in older}
        if len(slice_vals) < 2:
            continue
        lo = min(slice_vals.values())
        weak = {c for c, v in slice_vals.items() if v == lo}
        if len(weak) < len(slice_vals):
            pool = weak
            if len(pool) == 1:
                return next(iter(pool)), "lookback"
    return min(pool), "lex-min"


def winner(options: list[str], ballots: list[tuple[list[str], float]]) -> str:
    return str(recount(options, ballots)["winner"])
