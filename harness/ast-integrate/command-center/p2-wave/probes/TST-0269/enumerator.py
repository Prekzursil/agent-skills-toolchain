"""Exhaustive small-profile search for strategic-abstention advantage.

A hit is a (method, quorum, weights, focal seat, others' ballots) tuple where the
outcome when the focal seat ABSTAINS is not in the set of outcomes that seat can
obtain by casting any real ballot (A or B). That is the spec :11240 reading used
here: unique-by-not-voting, not merely a no-show paradox against the honest ballot.
"""
from __future__ import annotations

import json
from itertools import product
from typing import Any, Iterable

from tally import ABSTAIN, ALTERNATIVES, METHODS, config_key, tally

ACTIONS = ALTERNATIVES + (ABSTAIN,)
WEIGHTS_GRID = (
    (1, 1, 1),
    (3, 1, 1),
    (2, 2, 1),
    (1, 1, 1, 1),
)


def quorum_grid(weights: tuple[int, ...]) -> list[Any]:
    n = len(weights)
    total = sum(weights)
    heaviest = max(weights)
    lightest = min(weights)
    grid: list[Any] = [
        None,
        {"kind": "count", "min": 2},
        {"kind": "count", "min": n},
        {"kind": "weight", "min": total},
        {"kind": "weight", "min": heaviest + lightest},
    ]
    # Dedup equal numeric mins (equal-weight n=3: heaviest+lightest == 2, not total).
    seen: set[str] = set()
    out: list[Any] = []
    for q in grid:
        k = config_key("majority", q, weights)
        tag = k.split("|", 1)[1]
        if tag in seen:
            continue
        seen.add(tag)
        out.append(q)
    return out


def _assemble(n: int, focal: int, others: tuple[str, ...], vote: str) -> list[str]:
    ballots = [""] * n
    oj = 0
    for j in range(n):
        if j == focal:
            ballots[j] = vote
        else:
            ballots[j] = others[oj]
            oj += 1
    return ballots


def search_config(
    method: str, quorum: Any, weights: tuple[int, ...]
) -> list[dict[str, Any]]:
    n = len(weights)
    hits: list[dict[str, Any]] = []
    for focal in range(n):
        for others in product(ACTIONS, repeat=n - 1):
            o_abs = tally(
                _assemble(n, focal, others, ABSTAIN),
                method=method,
                weights=weights,
                quorum=quorum,
            )
            obtainable: dict[str, str] = {}
            for ballot in ALTERNATIVES:
                obtainable[ballot] = tally(
                    _assemble(n, focal, others, ballot),
                    method=method,
                    weights=weights,
                    quorum=quorum,
                )
            if o_abs in set(obtainable.values()):
                continue
            hits.append(
                {
                    "method": method,
                    "quorum": None if quorum is None else dict(quorum),
                    "weights": list(weights),
                    "focal": focal,
                    "focal_weight": int(weights[focal]),
                    "others": list(others),
                    "profile_with_abstention": _assemble(n, focal, others, ABSTAIN),
                    "outcome_abstain": o_abs,
                    "outcomes_by_ballot": obtainable,
                    "config_key": config_key(method, quorum, weights),
                }
            )
    return hits


def negative_control_hits(
    method: str = "majority", n: int = 3
) -> list[dict[str, Any]]:
    weights = tuple(1 for _ in range(n))
    return search_config(method, None, weights)


def iter_grid() -> Iterable[tuple[str, Any, tuple[int, ...]]]:
    for weights in WEIGHTS_GRID:
        for method in METHODS:
            for quorum in quorum_grid(weights):
                yield method, quorum, weights


def search_grid() -> dict[str, Any]:
    by_key: dict[str, dict[str, Any]] = {}
    n_configs = 0
    n_hits = 0
    for method, quorum, weights in iter_grid():
        n_configs += 1
        hits = search_config(method, quorum, weights)
        key = config_key(method, quorum, weights)
        n_hits += len(hits)
        if not hits:
            continue
        demo = hits[0]
        by_key[key] = {
            "method": method,
            "quorum": None if quorum is None else dict(quorum),
            "weights": list(weights),
            "n_profiles": len(hits),
            "demonstration": {
                "focal": demo["focal"],
                "focal_weight": demo["focal_weight"],
                "profile_with_abstention": demo["profile_with_abstention"],
                "outcome_abstain": demo["outcome_abstain"],
                "outcomes_by_ballot": demo["outcomes_by_ballot"],
            },
        }
    nc = negative_control_hits("majority", 3)
    nc_super = negative_control_hits("supermajority", 3)
    nc_unanim = negative_control_hits("unanimity", 3)
    return {
        "n_configs": n_configs,
        "n_vulnerable_configs": len(by_key),
        "n_advantage_profiles": n_hits,
        "triples": sorted(by_key.values(), key=lambda r: r["method"] + json.dumps(r, sort_keys=True)),
        "negative_control": {
            "method": "majority",
            "quorum": None,
            "weights": [1, 1, 1],
            "n_hits": len(nc),
            "supermajority_n_hits": len(nc_super),
            "unanimity_n_hits": len(nc_unanim),
        },
    }
