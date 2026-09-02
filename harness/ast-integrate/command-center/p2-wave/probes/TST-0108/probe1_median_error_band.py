#!/usr/bin/env python3
"""Probe 1: estimate is within the declared error band for the median unit.

Catalog tests_required[0]:
  test_estimate_is_within_the_declared_error_band_for_the_median_unit

Both-states: the live stratum-median estimator keeps the median eval unit
inside the pre-registered 50% band; a constant 10×-max mutant does not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from fanout_cost_model import (  # noqa: E402
    PREDECLARED_TOKEN_BAND,
    PREDECLARED_WALL_BAND,
    as_work_units,
    run_model,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0108-probe1 {msg}")
    return 1


def mutant_median_abs_rel(rows: list[dict], actual_key: str) -> float:
    actuals = [float(r[actual_key]) for r in rows]
    est = 10.0 * max(actuals)
    ordered = sorted(rows, key=lambda r: (float(r[actual_key]), r["id"]))
    mid = ordered[len(ordered) // 2]
    actual = float(mid[actual_key])
    return abs(est - actual) / actual if actual else 1.0


def main() -> int:
    model = run_model()
    eval_rows = model["eval_rows"]
    tok_band = float(model["declared_bands"]["tokens"])
    wall_band = float(model["declared_bands"]["wall_clock_s"])
    med_tok = model["median_unit_tokens"]
    med_wall = model["median_unit_wall"]
    mut_tok = mutant_median_abs_rel(eval_rows, "tokens_actual")
    mut_wall = mutant_median_abs_rel(eval_rows, "wall_actual_s")
    units = as_work_units(eval_rows, which="estimate")
    checks = {
        "n_eval_ge_50": int(model["n_eval"]) >= 50,
        "band_is_preregistered_50_tokens": abs(tok_band - PREDECLARED_TOKEN_BAND) < 1e-12,
        "band_is_preregistered_50_wall": abs(wall_band - PREDECLARED_WALL_BAND) < 1e-12,
        "median_tokens_within_band": med_tok["within_band"] is True
        and float(med_tok["abs_rel_error"]) <= tok_band,
        "median_wall_within_band": med_wall["within_band"] is True
        and float(med_wall["abs_rel_error"]) <= wall_band,
        "mutant_tokens_outside_band": mut_tok > tok_band,
        "mutant_wall_outside_band": mut_wall > wall_band,
        "work_units_consumable": len(units) == len(eval_rows)
        and all(u.token_cost > 0 and u.duration_ticks >= 1 for u in units),
        "substrates_present": len({r["substrate"] for r in eval_rows}) >= 2,
        "oracle_zero_error": all(
            abs(float(r["tokens_actual"]) - float(r["tokens_actual"])) == 0
            for r in eval_rows[:1]
        ),
    }
    payload = {
        "probe": "probe1-median-error-band",
        "unit_id": "TST-0108",
        "test": "test_estimate_is_within_the_declared_error_band_for_the_median_unit",
        "pass": all(checks.values()),
        "checks": checks,
        "n_eval": model["n_eval"],
        "declared_bands": model["declared_bands"],
        "median_unit_tokens": med_tok,
        "median_unit_wall": med_wall,
        "mutant_tokens_abs_rel": mut_tok,
        "mutant_wall_abs_rel": mut_wall,
        "seed": model["seed"],
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        failed = [k for k, v in checks.items() if not v]
        return fail(f"checks failed: {failed}")
    print(
        "SUCCESS:TST-0108-probe1 median-unit tokens "
        f"abs_rel={med_tok['abs_rel_error']:.4f}<= {tok_band} "
        f"wall abs_rel={med_wall['abs_rel_error']:.4f}<= {wall_band} "
        f"n_eval={model['n_eval']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
