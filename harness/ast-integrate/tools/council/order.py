"""Speaking-order strategy engine (IMP-0337).

Five pluggable production strategies decide who speaks when (round-robin,
random, priority, seniority-inverted, chair-recognition); an order-trace audit
checks that a *claimed* sequence is the one the strategy really produces; and a
first-speaker experiment measures whether speaking order biases the outcome.

The experiment's aggregator is a documented **anchoring plurality**: every
speaker casts one vote for its preference and the first speaker's vote carries
an extra ``bonus`` (default 3).  It is a deterministic stand-in for a live
council, not a claim about LLM or human deliberation.  A biased-order negative
control shows the detector fires when the unique dissenter is put first and
stays silent when the aggregator is order-blind (``bonus=0``).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

EXPERIMENT_N = 20
EXPERIMENT_SEED = 337
ANCHOR_BONUS = 3

PRODUCTION_STRATEGY_NAMES = (
    "round-robin",
    "random",
    "priority",
    "seniority-inverted",
    "chair-recognition",
)

# Hand-computed expectations for the four-seat seating chart used by the
# self-audit.  Index is the tie-break: alice(3,10,chair) bob(1,8) cara(2,2)
# drew(2,5).  Derived by hand from the strategy definitions, not by running
# ``speaking_order``.
HAND_ROSTER_SPEC: tuple[dict[str, Any], ...] = (
    {"seat_id": "alice", "priority": 3, "seniority": 10, "is_chair": True},
    {"seat_id": "bob", "priority": 1, "seniority": 8, "is_chair": False},
    {"seat_id": "cara", "priority": 2, "seniority": 2, "is_chair": False},
    {"seat_id": "drew", "priority": 2, "seniority": 5, "is_chair": False},
)
HAND_RANDOM_SEED = 7
HAND_EXPECTED: dict[tuple[str, int, tuple[str, ...] | None], list[str]] = {
    ("round-robin", 0, None): ["alice", "bob", "cara", "drew"],
    ("round-robin", 1, None): ["bob", "cara", "drew", "alice"],
    ("round-robin", 2, None): ["cara", "drew", "alice", "bob"],
    ("round-robin", 3, None): ["drew", "alice", "bob", "cara"],
    ("round-robin", 4, None): ["alice", "bob", "cara", "drew"],
    ("priority", 0, None): ["alice", "cara", "drew", "bob"],
    ("seniority-inverted", 0, None): ["cara", "drew", "bob", "alice"],
    ("chair-recognition", 0, None): ["alice", "bob", "cara", "drew"],
    ("chair-recognition", 0, ("drew", "cara", "bob")): ["alice", "drew", "cara", "bob"],
    ("random", 0, None): ["drew", "bob", "alice", "cara"],
    ("random", 1, None): ["alice", "bob", "drew", "cara"],
    ("random", 2, None): ["drew", "bob", "cara", "alice"],
}


@dataclass(frozen=True)
class Seat:
    """One council seat: identity plus the attributes strategies sort on."""

    seat_id: str
    priority: int = 0
    seniority: int = 0
    is_chair: bool = False


def list_strategies() -> tuple[str, ...]:
    """Names of the production strategies, in specification order."""
    return tuple(PRODUCTION_STRATEGY_NAMES)


def speaking_order(
    strategy: str,
    roster: Sequence[Seat],
    round_no: int = 0,
    round_index: int | None = None,
    recognition: Sequence[str] | None = None,
    rng_seed: int | None = None,
    **kwargs: Any,
) -> list[str]:
    """Return the speaking sequence ``strategy`` produces for ``roster``.

    * round-robin: rotate the roster left by the round index;
    * priority: higher ``priority`` first, roster index breaks ties;
    * seniority-inverted: lower ``seniority`` first (juniors speak before seniors);
    * chair-recognition: chairs first, then the chair's recognition list, then the rest;
    * random: ``random.Random(seed + 1009 * round)`` shuffle, reproducible per round.
    Unknown strategy names fall back to roster order.
    """
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
        seed = int(rng_seed) if rng_seed is not None else HAND_RANDOM_SEED
        rng = random.Random(seed + 1009 * int(round_no))
        out = list(ids)
        rng.shuffle(out)
        return out
    return ids


def audit_claimed(
    strategy: str, roster: Sequence[Seat], claimed: Sequence[str], **kwargs: Any
) -> dict[str, Any]:
    """Order-trace audit: does the claimed sequence equal what the strategy produces now?"""
    live = speaking_order(strategy, roster, **kwargs)
    match = list(claimed) == live
    return {
        "strategy": strategy,
        "ok": match,
        "match": match,
        "live": live,
        "claimed": list(claimed),
    }


def hand_roster() -> tuple[Seat, ...]:
    """The four-seat seating chart behind ``HAND_EXPECTED``."""
    return tuple(Seat(**row) for row in HAND_ROSTER_SPEC)


def audit_against_hand(
    cases: Mapping[tuple[str, int, tuple[str, ...] | None], Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Compare every strategy against the hand-computed sequences."""
    cases = dict(cases) if cases is not None else dict(HAND_EXPECTED)
    roster = hand_roster()
    rows: list[dict[str, Any]] = []
    for (name, rnd, rec), claimed in cases.items():
        kwargs: dict[str, Any] = {"round_index": rnd}
        if name == "random":
            kwargs["rng_seed"] = HAND_RANDOM_SEED
        if rec is not None:
            kwargs["recognition"] = list(rec)
        audit = audit_claimed(name, roster, list(claimed), **kwargs)
        rows.append(
            {
                "strategy": name,
                "round_index": rnd,
                "recognition": list(rec) if rec is not None else None,
                "claimed": list(claimed),
                "live": audit["live"],
                "match": audit["match"],
            }
        )
    return {"all_match": all(r["match"] for r in rows), "n": len(rows), "rows": rows}


def production_trace_audit(roster: Sequence[Seat] | None = None, rounds: int = 3) -> dict[str, Any]:
    """Record, for each strategy and round, the sequence produced and re-audit it."""
    seats = tuple(roster) if roster is not None else hand_roster()
    traces: list[dict[str, Any]] = []
    for name in PRODUCTION_STRATEGY_NAMES:
        for rnd in range(max(1, int(rounds))):
            kwargs: dict[str, Any] = {"round_index": rnd}
            if name == "random":
                kwargs["rng_seed"] = HAND_RANDOM_SEED
            produced = speaking_order(name, seats, **kwargs)
            audit = audit_claimed(name, seats, produced, **kwargs)
            traces.append(
                {
                    "strategy": name,
                    "round_index": rnd,
                    "sequence": produced,
                    "audit_match": audit["match"],
                }
            )
    return {"n_traces": len(traces), "traces": traces, "all_match": all(t["audit_match"] for t in traces)}


def decide_anchored(
    order: Sequence[str], prefs: Mapping[str, str], bonus: int = ANCHOR_BONUS
) -> dict[str, Any]:
    """Anchoring plurality: one vote per speaker, the first speaker's vote worth ``1 + bonus``.

    ``bonus=0`` is the order-blind plurality.  Ties resolve to ``"TIE"``.
    """
    scores: dict[str, int] = {}
    for option in sorted(set(prefs.values())):
        scores[option] = 0
    for position, seat in enumerate(order):
        choice = prefs[seat]
        scores[choice] = scores.get(choice, 0) + 1 + (int(bonus) if position == 0 else 0)
    top = max(scores.values()) if scores else 0
    leaders = sorted(option for option, score in scores.items() if score == top)
    winner = leaders[0] if len(leaders) == 1 else "TIE"
    first = order[0] if order else None
    return {
        "winner": winner,
        "scores": scores,
        "first_speaker": first,
        "first_preference": prefs[first] if first is not None else None,
        "bonus": int(bonus),
        "tie": winner == "TIE",
    }


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n == 0 or n != len(ys):
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0.0 or syy <= 0.0:
        return 0.0
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / ((sxx**0.5) * (syy**0.5))


def first_speaker_experiment(
    n: int | None = None,
    seed: int = EXPERIMENT_SEED,
    bonus: int = ANCHOR_BONUS,
    seats: Sequence[str] = ("W", "X", "Y", "Z"),
    options: Sequence[str] = ("adopt", "reject"),
) -> dict[str, Any]:
    """Run ``n`` matched pairs: same seats and preferences, shuffled order, different first speaker.

    Publishes the flip rate (pairs whose winner changed), the alignment rate of
    first speakers vs everyone else (a seat is *aligned* when the outcome equals
    its preference) and the Pearson correlation between "spoke first" and
    "aligned" over every seat-run.
    """
    n = int(n or EXPERIMENT_N)
    rng = random.Random(int(seed))
    seat_ids = list(seats)
    pairs: list[dict[str, Any]] = []
    is_first: list[float] = []
    aligned: list[float] = []
    counts = {
        "seat_runs": 0,
        "first_speaker_runs": 0,
        "first_speaker_aligned": 0,
        "not_first_runs": 0,
        "not_first_aligned": 0,
    }
    for _ in range(n):
        prefs = {s: rng.choice(list(options)) for s in seat_ids}
        while len(set(prefs.values())) < 2:  # a unanimous council cannot be swayed by order
            prefs = {s: rng.choice(list(options)) for s in seat_ids}
        order_a = list(seat_ids)
        rng.shuffle(order_a)
        order_b = list(seat_ids)
        rng.shuffle(order_b)
        while order_b[0] == order_a[0]:
            rng.shuffle(order_b)
        run_a = decide_anchored(order_a, prefs, bonus)
        run_b = decide_anchored(order_b, prefs, bonus)
        for order, run in ((order_a, run_a), (order_b, run_b)):
            for position, seat in enumerate(order):
                first = position == 0
                hit = run["winner"] == prefs[seat]
                is_first.append(1.0 if first else 0.0)
                aligned.append(1.0 if hit else 0.0)
                counts["seat_runs"] += 1
                if first:
                    counts["first_speaker_runs"] += 1
                    counts["first_speaker_aligned"] += int(hit)
                else:
                    counts["not_first_runs"] += 1
                    counts["not_first_aligned"] += int(hit)
        pairs.append(
            {
                "order_a": order_a,
                "order_b": order_b,
                "first_a": order_a[0],
                "first_b": order_b[0],
                "prefs_a": dict(prefs),
                "prefs_b": dict(prefs),
                "winner_a": run_a["winner"],
                "winner_b": run_b["winner"],
                "scores_a": run_a["scores"],
                "scores_b": run_b["scores"],
                "flipped": run_a["winner"] != run_b["winner"],
            }
        )
    flip_count = sum(1 for p in pairs if p["flipped"])
    rate_first = (
        counts["first_speaker_aligned"] / counts["first_speaker_runs"]
        if counts["first_speaker_runs"]
        else 0.0
    )
    rate_other = (
        counts["not_first_aligned"] / counts["not_first_runs"] if counts["not_first_runs"] else 0.0
    )
    return {
        "n_matched_pairs": len(pairs),
        "seed": int(seed),
        "bonus": int(bonus),
        "aggregator": "anchoring-plurality",
        "all_prefs_matched": all(p["prefs_a"] == p["prefs_b"] for p in pairs),
        "all_first_speakers_differ": all(p["first_a"] != p["first_b"] for p in pairs),
        "flip_count": flip_count,
        "flip_rate": flip_count / len(pairs) if pairs else 0.0,
        "alignment_rate_first_speaker": rate_first,
        "alignment_rate_not_first": rate_other,
        "first_speaker_alignment_delta": rate_first - rate_other,
        "pearson_first_speaker_vs_alignment": _pearson(is_first, aligned),
        "counts": counts,
        "pairs": pairs,
        "ok": bool(pairs),
    }


def negative_control_biased_order(bonus: int = ANCHOR_BONUS) -> dict[str, Any]:
    """Biased-order control on a unique-dissenter fixture (W, X, Y adopt; Z reject).

    Round-robin W,X,Y,Z lets the majority anchor; the biased order Z,W,X,Y puts
    the lone dissenter first.  Under anchoring the winner must flip (the
    detector fires); under the order-blind aggregator (``bonus=0``) both orders
    must agree with the plain plurality (the detector stays silent).
    """
    prefs = {"W": "adopt", "X": "adopt", "Y": "adopt", "Z": "reject"}
    round_robin = ["W", "X", "Y", "Z"]
    biased = ["Z", "W", "X", "Y"]
    rr = decide_anchored(round_robin, prefs, bonus)
    bi = decide_anchored(biased, prefs, bonus)
    rr_blind = decide_anchored(round_robin, prefs, 0)
    bi_blind = decide_anchored(biased, prefs, 0)
    plurality = rr_blind["winner"]
    fired = rr["winner"] != bi["winner"]
    silent = rr_blind["winner"] == bi_blind["winner"] == plurality
    return {
        "bonus": int(bonus),
        "prefs": prefs,
        "orders": {"round_robin": round_robin, "biased": biased},
        "winner_round_robin": rr["winner"],
        "winner_biased": bi["winner"],
        "winner_round_robin_order_blind": rr_blind["winner"],
        "winner_biased_order_blind": bi_blind["winner"],
        "winner_blind": rr_blind["winner"],
        "scores": {
            "round_robin": rr["scores"],
            "biased": bi["scores"],
            "round_robin_order_blind": rr_blind["scores"],
            "biased_order_blind": bi_blind["scores"],
        },
        "hand_tally": {
            "rr_winner": rr["winner"],
            "biased_winner": bi["winner"],
            "blind_winner": rr_blind["winner"],
            "rr_scores": rr["scores"],
            "biased_scores": bi["scores"],
            "blind_scores": rr_blind["scores"],
        },
        "fired_on_biased_order": fired,
        "silent_on_order_blind": silent,
        "detectable_effect": fired and silent,
        "ok": fired and silent,
    }
