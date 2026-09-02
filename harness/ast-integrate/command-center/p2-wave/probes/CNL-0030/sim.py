#!/usr/bin/env python3
"""Chair-led vs flat information-flow simulation for CNL-0030.

Two topologies, same per-reader token budget, same planted load-bearing seats.

Flat: complete graph. The recorder (seat 0) reads other full statements in
unprioritized seat order until the budget is spent. No agenda exists, so a
load-bearing claim at a high seat index costs the same as filler and is
dropped first.

Chair-led: star plus one synthesis broadcast. Every other seat spends 1 token
on a nomination flag (load-bearing or not). Remaining budget buys compact
agenda slots, scheduled load-bearing-first among flags the chair actually
read. Members do not read n-1 full statements.

Declared metric: load_bearing_recovery = |LB ∩ synthesis| / |LB|.
Chair-led beats flat when that fraction is strictly greater.
Crossover n = smallest sweep n at which chair-led beats flat.
Below crossover, recoveries are equal and chair-led is only tidier
(fewer messages).
"""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PARAMS_PATH = HERE / "fixtures" / "params.json"


def load_params(path: Path | None = None) -> dict[str, Any]:
    p = path or PARAMS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def load_bearing_seats(n: int) -> frozenset[int]:
    if n < 3:
        return frozenset(range(n))
    return frozenset({0, n - 2, n - 1})


def recovered_flat_set(n: int, params: dict[str, Any]) -> frozenset[int]:
    """Recorder seat 0; unprioritized inbound cursor over seats 1..n-1."""
    budget = int(params["read_budget_tokens"])
    stmt = int(params["flat_statement_tokens"])
    k = min(n - 1, budget // stmt)
    return frozenset({0} | set(range(1, k + 1)))


def recovered_chair_set(n: int, params: dict[str, Any]) -> frozenset[int]:
    """Chair seat 0; nomination pass then load-bearing-first compact slots."""
    budget = int(params["read_budget_tokens"])
    nom = int(params["nomination_tokens"])
    slot = int(params["chair_slot_tokens"])
    lb = load_bearing_seats(n)
    flags_read: list[int] = []
    spent = 0
    for seat in range(1, n):
        if spent + nom > budget:
            break
        spent += nom
        flags_read.append(seat)
    remaining = budget - spent
    capacity = remaining // slot
    lb_others = [s for s in flags_read if s in lb]
    rest = [s for s in flags_read if s not in lb]
    scheduled = (lb_others + rest)[:capacity]
    return frozenset({0} | set(scheduled))


def scheduled_count(n: int, params: dict[str, Any]) -> int:
    rec = recovered_chair_set(n, params)
    return len(rec) - 1


def recovery_fraction(recovered: frozenset[int], lb: frozenset[int]) -> Fraction:
    if not lb:
        return Fraction(1, 1)
    return Fraction(len(recovered & lb), len(lb))


def ratio_str(frac: Fraction) -> str:
    return f"{frac.numerator}/{frac.denominator}"


def flat_messages(n: int) -> int:
    """Directed full-statement hops on K_n (every member reads every other)."""
    return n * (n - 1)


def chair_messages(n: int, params: dict[str, Any]) -> int:
    """n-1 nomination flags + recognized compact slots + one synthesis artifact."""
    return (n - 1) + scheduled_count(n, params) + 1


def simulate_n(n: int, params: dict[str, Any]) -> dict[str, Any]:
    lb = load_bearing_seats(n)
    flat = recovered_flat_set(n, params)
    chair = recovered_chair_set(n, params)
    flat_r = recovery_fraction(flat, lb)
    chair_r = recovery_fraction(chair, lb)
    return {
        "n": n,
        "load_bearing_seats": sorted(lb),
        "flat_recovered_seats": sorted(flat),
        "chair_recovered_seats": sorted(chair),
        "flat_lb_recovered": sorted(flat & lb),
        "chair_lb_recovered": sorted(chair & lb),
        "flat_recovery": ratio_str(flat_r),
        "chair_recovery": ratio_str(chair_r),
        "flat_recovery_num": flat_r.numerator,
        "flat_recovery_den": flat_r.denominator,
        "chair_recovery_num": chair_r.numerator,
        "chair_recovery_den": chair_r.denominator,
        "chair_beats_flat": chair_r > flat_r,
        "flat_messages": flat_messages(n),
        "chair_messages": chair_messages(n, params),
        "chair_tidier_messages": chair_messages(n, params) < flat_messages(n),
    }


def sweep(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    p = params or load_params()
    return [simulate_n(int(n), p) for n in p["sweep_n"]]


def crossover_forward(rows: list[dict[str, Any]]) -> int | None:
    """Author path: first hit walking n ascending."""
    for row in rows:
        if row["chair_beats_flat"]:
            return int(row["n"])
    return None


def crossover_by_min(params: dict[str, Any] | None = None) -> int | None:
    """Reviewer path: rebuild recovered sets, then min() of the winning n's.

    Does not call crossover_forward and does not consume author row objects.
    """
    p = params or load_params()
    wins: list[int] = []
    for n in (int(x) for x in p["sweep_n"]):
        lb = load_bearing_seats(n)
        flat_r = recovery_fraction(recovered_flat_set(n, p), lb)
        chair_r = recovery_fraction(recovered_chair_set(n, p), lb)
        if chair_r > flat_r:
            wins.append(n)
    return min(wins) if wins else None


def check_crossover_claim(claimed: int, mechanical: int) -> str:
    """FIRE on a false crossover claim; SILENT when the claim matches."""
    if int(claimed) != int(mechanical):
        return "FIRE"
    return "SILENT"


def main() -> int:
    params = load_params()
    rows = sweep(params)
    author = crossover_forward(rows)
    reviewer = crossover_by_min(params)
    print(json.dumps({"author_crossover": author, "reviewer_crossover": reviewer, "rows": rows}, indent=2))
    return 0 if author == reviewer and author is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
