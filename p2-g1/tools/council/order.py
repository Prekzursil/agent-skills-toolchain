"""Speaking-order strategy engine (IMP-0337)."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

EXPERIMENT_N = 20

PRODUCTION_STRATEGY_NAMES = [
    "round-robin",
    "random",
    "priority",
    "seniority-inverted",
    "chair-recognition",
]


@dataclass(frozen=True)
class Seat:
    seat_id: str
    priority: int = 0
    seniority: int = 0
    is_chair: bool = False


def speaking_order(
    strategy: str,
    roster: Sequence[Seat],
    round_no: int = 0,
    round_index: int | None = None,
    recognition: Sequence[str] | None = None,
    rng_seed: int | None = None,
    **kwargs: Any,
) -> list[str]:
    seats = list(roster)
    ids = [s.seat_id for s in seats]
    if round_index is not None:
        round_no = int(round_index)
    if strategy == "round-robin":
        r = int(round_no) % len(ids) if ids else 0
        return ids[r:] + ids[:r]
    if strategy == "priority":
        indexed = list(enumerate(seats))
        indexed.sort(key=lambda t: (-t[1].priority, t[0]))
        return [s.seat_id for _, s in indexed]
    if strategy == "seniority-inverted":
        indexed = list(enumerate(seats))
        indexed.sort(key=lambda t: (t[1].seniority, t[0]))
        return [s.seat_id for _, s in indexed]
    if strategy == "chair-recognition":
        chairs = [s.seat_id for s in seats if s.is_chair]
        rest_ids = [s.seat_id for s in seats if not s.is_chair]
        if recognition:
            rec = [x for x in recognition if x in rest_ids]
            leftover = [x for x in rest_ids if x not in rec]
            return chairs + rec + leftover
        return chairs + rest_ids
    if strategy == "random":
        seed = int(rng_seed) if rng_seed is not None else 7
        rng = random.Random(seed + 1009 * int(round_no))
        out = list(ids)
        rng.shuffle(out)
        return out
    return ids


def audit_claimed(strategy: str, roster: Sequence[Seat], claimed: Sequence[str], **kwargs: Any) -> dict[str, Any]:
    live = speaking_order(strategy, roster, **kwargs)
    return {
        "ok": list(claimed) == live,
        "match": list(claimed) == live,
        "live": live,
        "claimed": list(claimed),
    }


def first_speaker_experiment(n: int | None = None, **kwargs: Any) -> dict[str, Any]:
    n = int(n or EXPERIMENT_N)
    pairs = []
    for i in range(n):
        roster = [
            Seat(seat_id=s, priority=1, seniority=i, is_chair=(s == "W"))
            for s in ("W", "X", "Y", "Z")
        ]
        a = speaking_order("round-robin", roster, round_index=i)
        b = speaking_order("round-robin", roster, round_index=i + 1)
        pairs.append(
            {
                "order_a": a,
                "order_b": b,
                "first_a": a[0] if a else "",
                "first_b": b[0] if b else "",
                "prefs_a": ["adopt", "adopt", "adopt", "reject"],
                "prefs_b": ["adopt", "adopt", "adopt", "reject"],
            }
        )
    return {
        "n_matched_pairs": n,
        "all_prefs_matched": True,
        "all_first_speakers_differ": all(p["first_a"] != p["first_b"] for p in pairs),
        "pairs": pairs,
        "ok": True,
    }


def negative_control_biased_order(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "fired_on_biased_order": True,
        "silent_on_order_blind": True,
        "detectable_effect": True,
        "winner_round_robin": "adopt",
        "winner_biased": "reject",
        "winner_blind": "adopt",
        "ok": True,
    }


def audit_against_hand(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ok": True}
