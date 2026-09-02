#!/usr/bin/env python3
"""Shared cardinal tabulation: approval is score voting restricted to {0,1}.

Declared BEFORE any ballot is seen (load-bearing; CNL-0062):
  * Domain: approval scores in {0, 1}; score votes in [L, H] with L < H.
  * Omitted candidate receives the declared floor L (default 0).
  * Per-ballot affine calibration onto [0, 1]: s' = (s - min) / (max - min).
    A flat ballot (max == min) contributes 0 to every candidate (uninformative).
  * Totals T[c] = sum_i weight_i * s'_i[c] as exact Fraction.
  * Winner = unique argmax(T). Ties broken by lexicographically smallest
    candidate_id, declared a priori so it cannot be picked to favour an outcome.
  * Seat weight defaults to 1. weight != 1 without a provenance record is
    rejected (CNL-0023 residual; this engine does not invent that record).

Two mechanically different reductions of the same calibrated ballots:
  * totals_row_major: accumulate per ballot, then per candidate
  * pairwise_score_margins: candidate X beats Y iff sum_i (s'_i[X] - s'_i[Y]) > 0
A unique argmax is a pairwise Condorcet winner of those margins; disagreement
is a bug, not a judgement call.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any


APPROVAL_DOMAIN = frozenset({0, 1, Fraction(0), Fraction(1)})


def as_frac(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not a score")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(value).limit_denominator(10_000_000)
    if isinstance(value, str):
        return Fraction(value)
    raise TypeError(f"unusable score type {type(value).__name__}")


def fill_scores(
    scores: dict[str, Any], candidates: list[str], floor: Fraction
) -> dict[str, Fraction]:
    filled: dict[str, Fraction] = {}
    for c in candidates:
        if c in scores:
            filled[c] = as_frac(scores[c])
        else:
            filled[c] = floor
    extra = set(scores) - set(candidates)
    if extra:
        raise ValueError(f"scores name unknown candidates {sorted(extra)}")
    return filled


def calibrate_ballot(
    scores: dict[str, Fraction], candidates: list[str]
) -> tuple[dict[str, Fraction], bool]:
    vals = [scores[c] for c in candidates]
    lo = min(vals)
    hi = max(vals)
    if hi == lo:
        return {c: Fraction(0) for c in candidates}, True
    span = hi - lo
    return {c: (scores[c] - lo) / span for c in candidates}, False


def check_domain(
    scores: dict[str, Fraction], kind: str, floor: Fraction, ceiling: Fraction
) -> None:
    if kind == "approval":
        bad = [c for c, s in scores.items() if s not in APPROVAL_DOMAIN]
        if bad:
            raise ValueError(f"approval scores not in {{0,1}}: {bad}")
        return
    if kind != "score":
        raise ValueError(f"unknown ballot kind {kind!r}")
    for c, s in scores.items():
        if s < floor or s > ceiling:
            raise ValueError(
                f"score {c}={s} outside declared [{floor}, {ceiling}]"
            )


def load_ballots(
    fixture: dict[str, Any],
    seat_ids: list[str] | None = None,
) -> tuple[list[str], list[dict[str, Any]], Fraction, Fraction]:
    candidates = list(fixture["candidates"])
    scale = fixture.get("scale") or {}
    floor = as_frac(scale.get("L", 0))
    ceiling = as_frac(scale.get("H", 10))
    if not (floor < ceiling):
        raise ValueError("scale requires L < H")
    wanted = set(seat_ids) if seat_ids is not None else None
    ballots = []
    for raw in fixture["ballots"]:
        sid = str(raw["seat_id"])
        if wanted is not None and sid not in wanted:
            continue
        kind = str(raw.get("kind") or "score")
        weight = as_frac(raw.get("weight", 1))
        provenance = raw.get("weight_provenance")
        if weight != 1 and not provenance:
            raise ValueError(
                f"seat {sid} weight={weight} lacks weight_provenance (CNL-0023)"
            )
        filled = fill_scores(raw["scores"], candidates, floor)
        check_domain(filled, kind, floor, ceiling)
        ballots.append(
            {
                "seat_id": sid,
                "kind": kind,
                "weight": weight,
                "raw": filled,
            }
        )
    if wanted is not None:
        got = {b["seat_id"] for b in ballots}
        missing = [s for s in seat_ids or [] if s not in got]
        if missing:
            raise ValueError(f"electorate seats missing: {missing}")
        order = {s: i for i, s in enumerate(seat_ids or [])}
        ballots.sort(key=lambda b: order[b["seat_id"]])
    return candidates, ballots, floor, ceiling


def positive_affine_map(
    src: dict[str, Fraction], dst: dict[str, Fraction], candidates: list[str]
) -> tuple[Fraction, Fraction] | None:
    """Return (a, b) with a>0 such that dst = a*src + b, or None."""
    pairs = [(src[c], dst[c]) for c in candidates]
    distinct = []
    seen = set()
    for s, d in pairs:
        if s in seen:
            continue
        seen.add(s)
        distinct.append((s, d))
    if len(distinct) < 2:
        return None
    (s0, d0), (s1, d1) = distinct[0], distinct[1]
    if s1 == s0:
        return None
    a = (d1 - d0) / (s1 - s0)
    if a <= 0:
        return None
    b = d0 - a * s0
    for s, d in pairs:
        if a * s + b != d:
            return None
    return a, b


def totals_row_major(
    calibrated: list[dict[str, Fraction]],
    weights: list[Fraction],
    candidates: list[str],
) -> dict[str, Fraction]:
    totals = {c: Fraction(0) for c in candidates}
    for w, scores in zip(weights, calibrated):
        for c in candidates:
            totals[c] += w * scores[c]
    return totals


def pairwise_score_margins(
    calibrated: list[dict[str, Fraction]],
    weights: list[Fraction],
    candidates: list[str],
) -> dict[tuple[str, str], Fraction]:
    """Different mechanism: signed margin of X vs Y, not the totals vector."""
    margins: dict[tuple[str, str], Fraction] = {}
    for i, x in enumerate(candidates):
        for y in candidates[i + 1 :]:
            m = Fraction(0)
            for w, scores in zip(weights, calibrated):
                m += w * (scores[x] - scores[y])
            margins[(x, y)] = m
            margins[(y, x)] = -m
    return margins


def argmax_winner(
    totals: dict[str, Fraction], candidates: list[str]
) -> tuple[str, bool]:
    best = max(totals[c] for c in candidates)
    tied = [c for c in candidates if totals[c] == best]
    tied.sort()
    return tied[0], len(tied) > 1


def pairwise_winner(
    margins: dict[tuple[str, str], Fraction], candidates: list[str]
) -> tuple[str, bool]:
    unbeaten: list[str] = []
    for x in candidates:
        lost = False
        for y in candidates:
            if x == y:
                continue
            if margins[(x, y)] < 0:
                lost = True
                break
        if not lost:
            unbeaten.append(x)
    unbeaten.sort()
    if not unbeaten:
        # Cycle of margins cannot occur for a linear score total, but if it
        # did we still apply the declared lex-min rule rather than inventing one.
        return sorted(candidates)[0], True
    return unbeaten[0], len(unbeaten) > 1


def tabulate(
    fixture: dict[str, Any],
    seat_ids: list[str] | None = None,
    *,
    calibrate: bool = True,
) -> dict[str, Any]:
    candidates, ballots, floor, ceiling = load_ballots(fixture, seat_ids)
    calibrated: list[dict[str, Fraction]] = []
    flats: list[str] = []
    weights: list[Fraction] = []
    for b in ballots:
        if calibrate:
            cal, flat = calibrate_ballot(b["raw"], candidates)
        else:
            cal, flat = b["raw"], False
        calibrated.append(cal)
        weights.append(b["weight"])
        if flat:
            flats.append(b["seat_id"])
    totals = totals_row_major(calibrated, weights, candidates)
    margins = pairwise_score_margins(calibrated, weights, candidates)
    w_tot, tie_tot = argmax_winner(totals, candidates)
    w_pair, tie_pair = pairwise_winner(margins, candidates)
    return {
        "candidates": candidates,
        "floor": str(floor),
        "ceiling": str(ceiling),
        "calibrate": calibrate,
        "n_ballots": len(ballots),
        "flat_ballots": flats,
        "totals": {c: str(totals[c]) for c in candidates},
        "totals_exact": totals,
        "winner_totals": w_tot,
        "totals_tied": tie_tot,
        "winner_pairwise": w_pair,
        "pairwise_tied": tie_pair,
        "signals_agree": w_tot == w_pair,
        "margins": {f"{a}>{b}": str(m) for (a, b), m in sorted(margins.items())},
        "seat_ids": [b["seat_id"] for b in ballots],
    }


def fraction_eq_map(a: dict[str, str], b: dict[str, Fraction]) -> bool:
    if set(a) != set(b):
        return False
    return all(Fraction(a[k]) == b[k] for k in a)
