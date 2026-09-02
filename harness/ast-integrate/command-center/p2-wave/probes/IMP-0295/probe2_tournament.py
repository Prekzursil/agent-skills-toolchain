#!/usr/bin/env python3
"""Probe 2: tournament + both-states negative control + store feed.

Recomputes payoffs from the exported (p, y) rows rather than trusting
ledger.totals(). Under Brier the hedger must not win; under the non-proper
hedge-reward rule the hedger must win. Same seed, same n.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.protocol.betting import (  # noqa: E402
    BrierPayoff,
    HedgeRewardPayoff,
    TOURNAMENT_N,
    TOURNAMENT_SEED,
    run_tournament,
)

ART = REPO / "command-center/receipts/IMP-0295.json"


def recompute_totals(store: dict, payoff_fn) -> dict[str, float]:
    out: dict[str, float] = {}
    for pid, rec in (store.get("participants") or {}).items():
        total = 0.0
        for row in rec.get("forecasts") or []:
            total += payoff_fn(float(row["p"]), int(row["outcome"]))
        out[pid] = total
    return out


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0295-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:IMP-0295-probe2 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:IMP-0295" not in json.dumps(doc):
        print("FAILED:IMP-0295-probe2 sentinel absent")
        return 1

    proper = run_tournament(seed=TOURNAMENT_SEED, n=TOURNAMENT_N, rule=BrierPayoff())
    mutant = run_tournament(
        seed=TOURNAMENT_SEED, n=TOURNAMENT_N, rule=HedgeRewardPayoff()
    )

    brier = BrierPayoff()
    hedge_rule = HedgeRewardPayoff()
    proper_re = recompute_totals(proper["store"], brier.payoff)
    mutant_re = recompute_totals(mutant["store"], hedge_rule.payoff)

    for name in ("committer", "hedger", "random"):
        if abs(proper_re[name] - proper["totals"][name]) > 1e-9:
            print("FAILED:IMP-0295-probe2 proper recompute mismatch", name, proper_re, proper["totals"])
            return 1
        if abs(mutant_re[name] - mutant["totals"][name]) > 1e-9:
            print("FAILED:IMP-0295-probe2 mutant recompute mismatch", name, mutant_re, mutant["totals"])
            return 1

    if proper["hedger_wins"] or not proper["committer_beats_hedger"]:
        print("FAILED:IMP-0295-probe2 hedger won under Brier", proper["ranking"], proper["totals"])
        return 1
    if proper["winner"] != "committer":
        print("FAILED:IMP-0295-probe2 expected committer first", proper["ranking"])
        return 1
    if not mutant["hedger_wins"] or mutant["winner"] != "hedger":
        print("FAILED:IMP-0295-probe2 hedger did not win under non-proper", mutant["ranking"])
        return 1
    if proper["hedger_wins"] == mutant["hedger_wins"]:
        print("FAILED:IMP-0295-probe2 negative control did not discriminate")
        return 1

    if proper["store"].get("schema") != "council.calibration.store.v1":
        print("FAILED:IMP-0295-probe2 store schema", proper["store"].get("schema"))
        return 1
    if proper["n_store_forecasts"] != 3 * TOURNAMENT_N:
        print(
            "FAILED:IMP-0295-probe2 store count",
            proper["n_store_forecasts"],
            "want",
            3 * TOURNAMENT_N,
        )
        return 1

    # Receipt tournament numbers must match this live re-run (same seed).
    rec_t = doc.get("tournament") or {}
    rec_totals = rec_t.get("totals") or {}
    for name in ("committer", "hedger", "random"):
        if name not in rec_totals:
            print("FAILED:IMP-0295-probe2 receipt missing tournament total", name)
            return 1
        if abs(float(rec_totals[name]) - proper["totals"][name]) > 1e-9:
            print(
                "FAILED:IMP-0295-probe2 receipt tournament drift",
                name,
                rec_totals[name],
                proper["totals"][name],
            )
            return 1
    if rec_t.get("ranking") != proper["ranking"]:
        print("FAILED:IMP-0295-probe2 receipt ranking drift", rec_t.get("ranking"), proper["ranking"])
        return 1

    rec_nc = doc.get("negative_control") or {}
    if rec_nc.get("discriminates") is not True:
        print("FAILED:IMP-0295-probe2 receipt negative_control.discriminates", rec_nc)
        return 1
    if rec_nc.get("nonproper_winner") != "hedger":
        print("FAILED:IMP-0295-probe2 receipt nonproper winner", rec_nc)
        return 1

    payload = {
        "probe": "probe2-tournament",
        "unit_id": "IMP-0295",
        "proper_winner": proper["winner"],
        "proper_totals": proper["totals"],
        "proper_ranking": proper["ranking"],
        "nonproper_winner": mutant["winner"],
        "nonproper_totals": mutant["totals"],
        "discriminates": True,
        "store_forecasts": proper["n_store_forecasts"],
        "recompute_matched": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    print("SUCCESS:IMP-0295-probe2 tournament hedger-loses and nonproper both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
