#!/usr/bin/env python3
"""Probe 1: strictly-proper scoring, hedging loses, unresolvable refused.

Recomputes expected Brier/log scores from closed form. Does not trust
betting.strictly_proper_report's boolean; it re-derives the maximiser.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.protocol.betting import (  # noqa: E402
    BettingError,
    BettingLedger,
    BrierPayoff,
    GRID,
    HedgeRewardPayoff,
    LinearHitPayoff,
    LogPayoff,
    Proposition,
)

ART = REPO / "command-center/receipts/IMP-0295.json"
LOG_CLIP = 1e-15


def local_brier_payoff(p: float, y: int) -> float:
    return 1.0 - (p - y) ** 2


def local_brier_expected(q: float, pi: float) -> float:
    return pi * local_brier_payoff(q, 1) + (1.0 - pi) * local_brier_payoff(q, 0)


def local_log_expected(q: float, pi: float) -> float:
    qq = min(1.0 - LOG_CLIP, max(LOG_CLIP, q))
    return pi * math.log(qq) + (1.0 - pi) * math.log(1.0 - qq)


def unique_max_is_truth(expected_fn, pi_grid) -> tuple[bool, list[float]]:
    bad: list[float] = []
    for pi in pi_grid:
        scored = [(q, expected_fn(q, pi)) for q in pi_grid]
        best_q, best_s = max(scored, key=lambda t: t[1])
        ties = [q for q, s in scored if abs(s - best_s) <= 1e-12]
        if not (len(ties) == 1 and abs(best_q - pi) <= 1e-12):
            bad.append(pi)
    return len(bad) == 0, bad


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0295-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:IMP-0295-probe1 self-declared", doc.get("state"))
        return 1
    blob = json.dumps(doc)
    if "SUCCESS:IMP-0295" not in blob:
        print("FAILED:IMP-0295-probe1 sentinel absent")
        return 1

    brier = BrierPayoff()
    log = LogPayoff()
    # Module payoff must match the closed form the probe owns.
    for p, y in ((0.2, 0), (0.2, 1), (0.5, 0), (0.5, 1), (0.9, 1), (0.9, 0)):
        got = brier.payoff(p, y)
        want = local_brier_payoff(p, y)
        if abs(got - want) > 1e-12:
            print(f"FAILED:IMP-0295-probe1 brier mismatch p={p} y={y} {got}!={want}")
            return 1

    ok_b, bad_b = unique_max_is_truth(local_brier_expected, GRID)
    ok_l, bad_l = unique_max_is_truth(local_log_expected, GRID)
    if not ok_b:
        print("FAILED:IMP-0295-probe1 brier not strictly proper", bad_b)
        return 1
    if not ok_l:
        print("FAILED:IMP-0295-probe1 log not strictly proper", bad_l)
        return 1

    # Hedging loses whenever true pi != 0.5.
    hedge_losses = []
    for pi in GRID:
        if abs(pi - 0.5) <= 1e-12:
            continue
        if not (local_brier_expected(pi, pi) > local_brier_expected(0.5, pi) + 1e-12):
            hedge_losses.append(pi)
        if not (local_log_expected(pi, pi) > local_log_expected(0.5, pi) + 1e-12):
            hedge_losses.append(pi)
    if hedge_losses:
        print("FAILED:IMP-0295-probe1 hedge did not lose", hedge_losses)
        return 1

    # Pathwise: committer who is right beats 0.5.
    for p, y in ((0.9, 1), (0.8, 1), (0.3, 0), (0.1, 0)):
        if not (brier.payoff(p, y) > brier.payoff(0.5, y)):
            print(f"FAILED:IMP-0295-probe1 pathwise p={p} y={y}")
            return 1
        if not (log.payoff(p, y) > log.payoff(0.5, y)):
            print(f"FAILED:IMP-0295-probe1 pathwise-log p={p} y={y}")
            return 1

    # Negative labels: hedge-reward and linear-hit are NOT strictly proper.
    ok_h, _ = unique_max_is_truth(
        lambda q, pi: HedgeRewardPayoff().payoff(q, 0), GRID
    )
    if ok_h:
        print("FAILED:IMP-0295-probe1 hedge-reward looked strictly proper")
        return 1
    linear_best = []
    for pi in (0.2, 0.8):
        scored = [
            (
                q,
                pi * LinearHitPayoff().payoff(q, 1)
                + (1 - pi) * LinearHitPayoff().payoff(q, 0),
            )
            for q in GRID
        ]
        best_q = max(scored, key=lambda t: t[1])[0]
        linear_best.append(best_q)
    if 0.2 in linear_best or 0.8 in linear_best:
        # linear hit maximises at the extreme, not at truth
        pass
    if any(abs(q - 1.0) < 1e-9 or q == max(GRID) for q in linear_best):
        linear_ok = True
    else:
        linear_ok = False
    if not linear_ok:
        print("FAILED:IMP-0295-probe1 linear-hit did not extremise", linear_best)
        return 1

    ledger = BettingLedger()
    refused = False
    try:
        ledger.add_proposition(
            Proposition(
                proposition_id="unresolvable",
                statement="vague claim",
                resolution_criterion="   ",
            )
        )
    except BettingError:
        refused = True
    if not refused:
        print("FAILED:IMP-0295-probe1 unresolvable proposition was accepted")
        return 1

    ledger.add_proposition(
        Proposition(
            proposition_id="rain-monday",
            statement="it will rain Monday 09:00-18:00 at the site gauge",
            resolution_criterion="site gauge records >=0.2 mm between those timestamps",
        )
    )
    ledger.stake("alice", "rain-monday", 0.8)
    ledger.resolve("rain-monday", 1)
    if abs(ledger.totals()["alice"] - brier.payoff(0.8, 1)) > 1e-12:
        print("FAILED:IMP-0295-probe1 settlement mismatch", ledger.totals())
        return 1
    store = ledger.store.to_dict()
    if store.get("schema") != "council.calibration.store.v1":
        print("FAILED:IMP-0295-probe1 store schema", store.get("schema"))
        return 1
    fc = store["participants"]["alice"]["forecasts"]
    if fc[0]["p"] != 0.8 or fc[0]["outcome"] != 1:
        print("FAILED:IMP-0295-probe1 store row", fc)
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-strictly-proper",
                "unit_id": "IMP-0295",
                "brier_strictly_proper": True,
                "log_strictly_proper": True,
                "hedging_loses": True,
                "pathwise_committer_ahead": True,
                "unresolvable_refused": True,
                "store_fed": True,
                "linear_hit_extremises": True,
                "hedge_reward_not_proper": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0295-probe1 strictly-proper scoring and hedge-loses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
