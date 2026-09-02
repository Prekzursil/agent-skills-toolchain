#!/usr/bin/env python3
"""Probe 2: independent arithmetic + mutant controls.

Recompute MAPE and bias from the published rows. Folding NOT-CHECKED into
pass must change MAPE and must not be what the artifact published. Cost
computed from last-turn tokens must not match the published cost on the
multi-turn workflow.
"""
from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import calibrate as C  # noqa: E402
from calibrate import (  # noqa: E402
    aggregates_from_rows,
    bias_direction,
    folded_mape_if_not_checked_were_zero,
    mape_pct,
)
from ledger import USD_PER_TOKEN, cost_usd  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0081-estimate-accuracy.json"


def close(a, b) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-15)


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0081-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = C.report_body(doc)
    rows = body.get("rows") or []
    if len(rows) < 2:
        print("FAILED:CNF-0081-probe2 too few rows")
        return 1

    recomputed = aggregates_from_rows(rows)
    published = body.get("aggregates") or {}
    print(
        json.dumps(
            {
                "recomputed_mape": recomputed["mape_cost_pct"],
                "published_mape": published.get("mape_cost_pct"),
                "recomputed_bias": recomputed["bias_direction"],
                "published_bias": published.get("bias_direction"),
                "n_measured": recomputed["n_measured"],
                "n_not_checked": recomputed["n_not_checked"],
            },
            sort_keys=True,
        )
    )
    if not close(recomputed["mape_cost_pct"], published.get("mape_cost_pct")):
        print("FAILED:CNF-0081-probe2 MAPE does not recompute")
        return 1
    if recomputed["bias_direction"] != published.get("bias_direction"):
        print("FAILED:CNF-0081-probe2 bias_direction does not recompute")
        return 1
    if recomputed["order_of_magnitude_overruns"] != published.get(
        "order_of_magnitude_overruns"
    ):
        print("FAILED:CNF-0081-probe2 oom list does not recompute")
        return 1
    if published.get("bias_direction") == published.get("bias_magnitude"):
        print("FAILED:CNF-0081-probe2 bias direction collapsed into magnitude")
        return 1

    honest = mape_pct(
        [
            (float(r["estimate"]["cost_usd"]), float(r["observed"]["cost_usd"]))
            for r in rows
            if r.get("status") == "MEASURED"
        ]
    )
    folded = folded_mape_if_not_checked_were_zero(rows)
    print(f"honest_mape={honest} folded_mape={folded}")
    if folded is None or honest is None or close(honest, folded):
        print("FAILED:CNF-0081-probe2 NOT-CHECKED fold control inert")
        return 1
    if not close(published.get("mape_cost_pct"), honest):
        print("FAILED:CNF-0081-probe2 published MAPE is not the honest one")
        return 1

    mutant = copy.deepcopy(doc)
    mutant_rows = C.report_body(mutant).get("rows") or []
    for row in mutant_rows:
        if row.get("status") == "NOT-CHECKED" and row.get("estimate"):
            est = row["estimate"]
            row["status"] = "MEASURED"
            row["observed"] = {
                "cost_usd": est["cost_usd"],
                "tokens_cumulative": est["tokens_cumulative"],
                "tokens_last_turn": est["tokens_cumulative"],
                "wall_clock_s": est["wall_clock_s"],
                "n_turns": 1,
                "writes": est.get("blast_radius") or [],
            }
            row["error"] = {
                "cost_signed_pct": 0.0,
                "cost_abs_pct": 0.0,
                "order_of_magnitude_cost": False,
            }
    mutant_agg = aggregates_from_rows(mutant_rows)
    print(f"mutant_folded_mape={mutant_agg['mape_cost_pct']}")
    if close(mutant_agg["mape_cost_pct"], honest):
        print("FAILED:CNF-0081-probe2 folding NOT-CHECKED did not change MAPE")
        return 1

    multi = next((r for r in rows if r.get("id") == "wf.turns.cumulative"), None)
    if not multi or multi.get("status") != "MEASURED":
        print("FAILED:CNF-0081-probe2 multi-turn row missing")
        return 1
    obs = multi["observed"]
    if obs["tokens_cumulative"] == obs["tokens_last_turn"]:
        print("FAILED:CNF-0081-probe2 cumulative equals last-turn")
        return 1
    if not close(obs["cost_usd"], cost_usd(obs["tokens_cumulative"])):
        print("FAILED:CNF-0081-probe2 cost not from cumulative")
        return 1
    if close(obs["cost_usd"], cost_usd(obs["tokens_last_turn"])):
        print("FAILED:CNF-0081-probe2 cost matches last-turn (conflation)")
        return 1
    last_turn_pairs = []
    for r in rows:
        if r.get("status") != "MEASURED":
            continue
        last_turn_pairs.append(
            (
                float(r["estimate"]["cost_usd"]),
                float(r["observed"]["tokens_last_turn"]) * USD_PER_TOKEN,
            )
        )
    conflated_mape = mape_pct(last_turn_pairs)
    print(f"last_turn_mape={conflated_mape} direction={bias_direction(last_turn_pairs)}")
    if close(conflated_mape, honest):
        print("FAILED:CNF-0081-probe2 last-turn MAPE indistinguishable from cumulative")
        return 1

    unnamed = [r["id"] for r in rows if not r.get("accounting_source")]
    if unnamed:
        print("FAILED:CNF-0081-probe2 unnamed accounting", unnamed)
        return 1
    bad_status = [
        r["id"]
        for r in rows
        if r.get("status") not in {"MEASURED", "NOT-CHECKED", "EXCLUDED", "INSUFFICIENT"}
    ]
    if bad_status:
        print("FAILED:CNF-0081-probe2 bad status", bad_status)
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        print("FAILED:CNF-0081-probe2 reviewer not independent")
        return 1

    print(
        "overclaim_ok=True arithmetic_ok=True "
        f"honest_mape={honest} folded_mape={folded} "
        f"last_turn_mape={conflated_mape}"
    )
    print("SUCCESS:CNF-0081-probe2 reviewer arithmetic and mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
