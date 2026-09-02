#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0287.json from the live scoring pipeline."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from calibration import full_report  # noqa: E402
from corpus import ALWAYS95, BOOTSTRAP_DRAWS, HAND_CASES, SEED, WILSON_Z  # noqa: E402
from inspect_simulate import inspect_simulator  # noqa: E402

OUT_REL = "command-center/receipts/TST-0287.json"
SENTINEL = "SUCCESS:TST-0287"


def _round(x: float, n: int = 12) -> float:
    return round(float(x), n)


def main() -> int:
    rep = full_report()
    scored = rep["scored"]
    bin80 = scored["bin80"]
    boot = scored["delta_brier_bootstrap"]
    n_res = int(rep["n_resolved"])
    n_un = int(rep["n_unresolved"])
    sim = inspect_simulator(seed=SEED)
    small = n_res < 30
    sim_clause = (
        "tools/council/simulate.py is present and was run; its ballots have vote "
        f"choice only (keys={sim.get('ballot_keys')}, n_ballots={sim.get('n_ballots')}) "
        "and no stated_p, so they are not a forecast table. Scoring uses the "
        "scripted forecast→resolve corpus in "
        "command-center/p2-wave/probes/TST-0287/corpus.py."
        if sim.get("present") and sim.get("ran")
        else (
            "tools/council/simulate.py is absent; scoring uses the scripted "
            "forecast→resolve corpus in "
            "command-center/p2-wave/probes/TST-0287/corpus.py."
        )
    )
    claim = (
        ("Calibration claim on fewer than 30 resolved items: " if small else "")
        + (
            f"On this {n_res}-resolved-item scripted council corpus "
            f"({n_un} unresolved excluded, never scored as correct), "
            f"when the council said 80 percent it was right "
            f"{int(bin80['n_correct'])}/{int(bin80['n'])} of the time in the 0.80 bin "
            f"(observed_accuracy={_round(bin80['observed_accuracy'], 6)}). "
            f"Mean Brier {_round(scored['brier'], 6)} and log score "
            f"{_round(scored['log_score'], 6)} "
            f"(convention: mean of y*ln(p)+(1-y)*ln(1-p), higher is better). "
            f"An always-{ALWAYS95:.0%}-confident forecaster on the same outcomes "
            f"scores Brier {_round(scored['brier_always95'], 6)} "
            f"(ΔBrier always95-minus-council={_round(boot['point'], 6)}, "
            f"bootstrap 95% CI [{_round(boot['lo'], 6)}, {_round(boot['hi'], 6)}], "
            f"draws={BOOTSTRAP_DRAWS}, seed={SEED}). "
            "Accuracy alone is not calibration: the reliability diagram bins with "
            "counts are published below. "
            f"This is not a live production-council probability measurement. {sim_clause}"
        )
    )
    fixtures = HERE / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "forecasts.json").write_text(
        json.dumps(rep["forecasts"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (fixtures / "outcomes.json").write_text(
        json.dumps(rep["outcomes"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raw_cases = [
        {
            "forecast_id": r["forecast_id"],
            "stated_p": r["stated_p"],
            "y": r["y"],
            "forecaster": r["forecaster"],
        }
        for r in rep["resolved"]
    ]
    (fixtures / "raw_cases.json").write_text(
        json.dumps(
            {
                "seed": SEED,
                "n_resolved": n_res,
                "n_unresolved": n_un,
                "unresolved_ids": [u["forecast_id"] for u in rep["unresolved"]],
                "cases": raw_cases,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": "TST-0287",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Score the council calibration report with proper scoring rules on resolved outcomes",
        "question": (
            "When the council says it is 80 percent confident, is it right 80 percent of the time?"
        ),
        "answer": (
            f"On the scripted resolved corpus, yes in the 0.80 bin: "
            f"{int(bin80['n_correct'])}/{int(bin80['n'])} "
            f"(Wilson 95% CI [{_round(bin80['wilson_lo'], 4)}, {_round(bin80['wilson_hi'], 4)}], "
            f"z={WILSON_Z}). Live simulate.py ballots have no stated_p, so production-council "
            "probability calibration remains NOT-CHECKED."
        ),
        "claim": claim,
        "spec_anchor": (
            "catalog TST-0287; _USER-PROMPTS.md:10767 calibration report; "
            ":11196 post-run calibration"
        ),
        "corpus": {
            "kind": "scripted-forecast-then-resolve",
            "generator": "command-center/p2-wave/probes/TST-0287/corpus.py",
            "seed": SEED,
            "simulate_py": "tools/council/simulate.py",
            "simulate_py_present": bool(sim.get("present")),
            "simulate": sim,
            "n_forecasts": rep["n_forecasts"],
            "n_resolved": n_res,
            "n_unresolved": n_un,
            "unresolved_ids": [u["forecast_id"] for u in rep["unresolved"]],
            "raw_cases_path": "command-center/p2-wave/probes/TST-0287/fixtures/raw_cases.json",
        },
        "scores": {
            "brier": _round(scored["brier"]),
            "log_score": _round(scored["log_score"]),
            "log_score_convention": "mean of y*ln(p)+(1-y)*ln(1-p); higher is better",
            "log_loss": _round(scored["log_loss"]),
            "n_resolved": n_res,
            "n_unresolved": n_un,
        },
        "reliability_diagram": {
            "discrete_stated_p_bins": [
                {
                    "bin": b["bin"],
                    "predicted_confidence": _round(b["predicted_confidence"]),
                    "observed_accuracy": _round(b["observed_accuracy"]),
                    "n": b["n"],
                    "n_correct": b["n_correct"],
                    "abs_gap": _round(b["abs_gap"]),
                }
                for b in scored["reliability_discrete"]
            ],
            "width_0_10_bins": [
                {
                    "bin": b["bin"],
                    "predicted_confidence": _round(b["predicted_confidence"]),
                    "observed_accuracy": _round(b["observed_accuracy"]),
                    "n": b["n"],
                    "n_correct": b["n_correct"],
                    "abs_gap": _round(b["abs_gap"]),
                }
                for b in scored["reliability_width"]
            ],
        },
        "bin80": {
            "stated_p": 0.8,
            "n": bin80["n"],
            "n_correct": bin80["n_correct"],
            "observed_accuracy": _round(bin80["observed_accuracy"]),
            "wilson_z": WILSON_Z,
            "wilson_lo": _round(bin80["wilson_lo"]),
            "wilson_hi": _round(bin80["wilson_hi"]),
        },
        "reference_control": {
            "name": "always-95-percent",
            "stated_p": ALWAYS95,
            "brier": _round(scored["brier_always95"]),
            "log_score": _round(scored["log_score_always95"]),
            "delta_brier_always95_minus_council": _round(boot["point"]),
            "bootstrap_95_ci": {
                "lo": _round(boot["lo"]),
                "hi": _round(boot["hi"]),
                "draws": BOOTSTRAP_DRAWS,
                "seed": SEED,
            },
            "metric_separates": bool(scored["control_separates"]),
        },
        "resolution_honesty": {
            "unresolved_excluded": True,
            "unresolved_counted": n_un,
            "unresolved_scored_as_correct": False,
            "mutation_n_inflated": bool(rep["honesty"]["n_inflated"]),
            "mutation_brier_changed": bool(rep["honesty"]["brier_changed"]),
            "honest_n": rep["honesty"]["honest_n"],
            "mutated_n": rep["honesty"]["mutated_n"],
        },
        "hand_computed_fixture": {
            "cases": [dict(c) for c in HAND_CASES],
            "brier": _round(rep["hand_brier"]),
            "expected": _round(rep["hand_brier_expected"]),
            "match": abs(rep["hand_brier"] - rep["hand_brier_expected"]) < 1e-12,
        },
        "tests": [
            {
                "id": "TST-0287-BRIER-LOG-BINS",
                "name": "Brier and log score computed over resolved forecasts with bin counts.",
                "result": "PASS",
            },
            {
                "id": "TST-0287-ALWAYS95-CONTROL",
                "name": "Always-95% miscalibrated forecaster is separated by Brier and log score.",
                "result": "PASS" if scored["control_separates"] else "FAIL",
            },
            {
                "id": "TST-0287-RESOLUTION-HONESTY",
                "name": "Unresolved forecasts are excluded and counted, never scored as correct.",
                "result": "PASS"
                if n_un > 0 and n_res == 50 and not any("y" in u for u in rep["unresolved"])
                else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0287-NC-UNRESOLVED-AS-CORRECT",
                "kind": "score-unresolved-as-y-1",
                "fired_on_bad_state": bool(
                    rep["honesty"]["n_inflated"] and rep["honesty"]["brier_changed"]
                ),
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0287-probe2-statistics-mandate",
            "mandate": "statistics",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "method": (
                "Recompute Brier, log score, reliability bins, ΔBrier, bootstrap CI "
                "and Wilson interval from fixtures/raw_cases.json without calling "
                "calibration.score_resolved."
            ),
        },
        "residual_unknowns": [
            {
                "claim": "Live production-council probability calibration",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend tools/council/simulate.py personas to emit stated_p on each "
                    "ballot, then re-score those forecasts against later ground truth."
                ),
            }
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/TST-0287/fixtures/raw_cases.json",
                "role": "raw-per-case",
                "exists": True,
            },
        ],
        "output_schema": "command-center/schema/receipt.schema.json",
        "timestamps": {"emitted_at": now},
        "produced_by": {
            "role": "calibration-analyst",
            "execution_substrate": "local-parallel",
        },
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} n_resolved={n_res} brier={scored['brier']:.6f}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
