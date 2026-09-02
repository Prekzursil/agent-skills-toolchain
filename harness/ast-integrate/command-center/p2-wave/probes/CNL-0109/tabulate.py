"""IRV vs calibrated-score knapsack on a shared non-exclusive option set."""
from __future__ import annotations

from collections import Counter
from typing import Any


def irv_winner(ballots: list[list[str]], candidates: list[str]) -> str | None:
    remaining = set(candidates)
    while remaining:
        first: Counter[str] = Counter()
        for ballot in ballots:
            for choice in ballot:
                if choice in remaining:
                    first[choice] += 1
                    break
        if not first:
            return None
        total = sum(first.values())
        majority = [c for c, n in first.items() if n * 2 > total]
        if majority:
            return sorted(majority)[0]
        lowest = min(first.get(c, 0) for c in remaining)
        losers = sorted(c for c in remaining if first.get(c, 0) == lowest)
        remaining.remove(losers[0])
        if len(remaining) == 1:
            return next(iter(remaining))
    return None


def irv_elimination_order(ballots: list[list[str]], candidates: list[str]) -> list[str]:
    remaining = set(candidates)
    eliminated: list[str] = []
    while remaining:
        first: Counter[str] = Counter()
        for ballot in ballots:
            for choice in ballot:
                if choice in remaining:
                    first[choice] += 1
                    break
        if not first:
            break
        total = sum(first.values())
        majority = [c for c, n in first.items() if n * 2 > total]
        if majority or len(remaining) == 1:
            winner = sorted(majority)[0] if majority else next(iter(remaining))
            rest = sorted(c for c in remaining if c != winner)
            return [winner] + rest
        lowest = min(first.get(c, 0) for c in remaining)
        losers = sorted(c for c in remaining if first.get(c, 0) == lowest)
        remaining.remove(losers[0])
        eliminated.append(losers[0])
    return list(reversed(eliminated))


def fund_by_order(order: list[str], items: dict[str, dict[str, int]], budget: int) -> dict[str, Any]:
    chosen: list[str] = []
    spent = 0
    value = 0
    for cid in order:
        cost = int(items[cid]["cost"])
        if spent + cost <= budget:
            chosen.append(cid)
            spent += cost
            value += int(items[cid]["value"])
    return {"set": chosen, "spent": spent, "value": value, "order": order}


def knapsack(items: dict[str, dict[str, int]], budget: int) -> dict[str, Any]:
    ids = list(items)
    n = len(ids)
    best_value = -1
    best_set: list[str] = []
    best_spent = 0
    for mask in range(1 << n):
        spent = 0
        value = 0
        chosen: list[str] = []
        for i, cid in enumerate(ids):
            if mask & (1 << i):
                spent += int(items[cid]["cost"])
                value += int(items[cid]["value"])
                chosen.append(cid)
        if spent <= budget and (
            value > best_value
            or (value == best_value and spent < best_spent)
            or (value == best_value and spent == best_spent and chosen < best_set)
        ):
            best_value = value
            best_set = chosen
            best_spent = spent
    return {"set": best_set, "spent": best_spent, "value": best_value}


def trap_fixture() -> dict[str, Any]:
    """Options are jointly fundable. IRV treats them as exclusive substitutes."""
    items = {
        "A": {"cost": 3, "value": 5, "label": "small-high-density-1"},
        "B": {"cost": 3, "value": 5, "label": "small-high-density-2"},
        "C": {"cost": 5, "value": 8, "label": "shiny-large"},
        "D": {"cost": 4, "value": 2, "label": "filler"},
    }
    budget = 6
    ballots = (
        [["C", "A", "B", "D"]] * 3
        + [["C", "B", "A", "D"]] * 2
        + [["A", "B", "C", "D"]]
        + [["B", "A", "C", "D"]]
    )
    winner = irv_winner(ballots, list(items))
    order = irv_elimination_order(ballots, list(items))
    irv_portfolio = fund_by_order(order, items, budget)
    score = knapsack(items, budget)
    return {
        "items": items,
        "budget": budget,
        "ballots": ballots,
        "ballot_count": len(ballots),
        "irv_winner": winner,
        "irv_funding_order": order,
        "irv_portfolio": irv_portfolio,
        "knapsack": score,
        "trap_fires": bool(
            winner == "C"
            and score["value"] > irv_portfolio["value"]
            and set(score["set"]) == {"A", "B"}
        ),
        "why": (
            "IRV elects a single substitute (C) because it assumes mutually "
            "exclusive alternatives. Funding along the IRV order then spends "
            "the budget on C and cannot also take A or B. Calibrated score + "
            "knapsack funds A+B, the feasible set with higher total value. "
            "Ranked-choice has no representation of 'both A and B'."
        ),
    }
