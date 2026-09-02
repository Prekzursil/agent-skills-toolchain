#!/usr/bin/env python3
"""Probe 2: negative control + both-states overconfidence detector.

The check is meant to REJECT independence-assuming aggregation when the
panel is correlated. On independent seats (tau=0) it must be SILENT:
p_indep_bayes equals p_true.

Mechanism: closed-form identity llr_indep == llr_true at tau=0, plus a
both-states detector on Monte Carlo mean |dp|. Distinct from probe 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import pool as P  # noqa: E402

OUT = HERE / "probe2-negative-control.raw.json"
ART = (
    REPO
    / "command-center/design/council/CNL-0065-bayesian-belief-aggregation-linear-versus-logarithmic-pool.md"
)
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
FIRE_MIN = 0.08
SILENT_MAX = 1e-12


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0065-probe2 {msg}")
    return 1


def detector(mean_abs_dp: float) -> str:
    return "FIRE" if mean_abs_dp >= FIRE_MIN else "SILENT"


def main() -> int:
    indep = P.monte_carlo(tau=P.TAU_INDEPENDENT)
    corr = P.monte_carlo(tau=P.TAU_CORRELATED)
    xs = P.CANONICAL_X
    llr_t = P.llr_true(xs, P.MU, P.SIGMA, P.TAU_INDEPENDENT)
    llr_i = P.llr_indep_bayes(xs, P.MU, P.SIGMA, P.TAU_INDEPENDENT)
    if abs(llr_t - llr_i) > 1e-15:
        return fail(f"tau=0 llr identity broken {llr_t} vs {llr_i}")
    a0 = P.aggregates(xs, P.MU, P.SIGMA, P.TAU_INDEPENDENT)
    if a0["abs_dp_indep"] > SILENT_MAX:
        return fail(f"tau=0 canonical dp {a0['abs_dp_indep']}")
    if indep["mean_abs_dp_indep"] > SILENT_MAX:
        return fail(f"tau=0 MC dp {indep['mean_abs_dp_indep']}")
    inf0 = P.inflation_factor(P.N_SEATS, P.SIGMA, P.TAU_INDEPENDENT)
    if abs(inf0 - 1.0) > 1e-15:
        return fail(f"tau=0 inflation {inf0} != 1")

    if detector(indep["mean_abs_dp_indep"]) != "SILENT":
        return fail("detector FIRED on independent (negative-control) panel")
    if detector(corr["mean_abs_dp_indep"]) != "FIRE":
        return fail("detector SILENT on correlated panel")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    g_errs = list(validator.iter_errors(garbage))
    if not g_errs:
        return fail("schema accepted garbage (vacuous schema)")

    payload = {
        "probe": "probe2-negative-control",
        "unit_id": "CNL-0065",
        "negative_control_state": "independent-seats tau=0",
        "negative_control_action": (
            "overconfidence detector is SILENT: independence-assuming "
            "Bayes equals the joint posterior, inflation_factor=1"
        ),
        "reject_state": "same-vendor correlated seats tau=1.5",
        "fired_on_correlated": True,
        "silent_on_independent": True,
        "independent_mean_abs_dp_indep": indep["mean_abs_dp_indep"],
        "correlated_mean_abs_dp_indep": corr["mean_abs_dp_indep"],
        "tau0_inflation_factor": inf0,
        "tau0_canonical_llr_true": llr_t,
        "tau0_canonical_llr_indep": llr_i,
        "schema_garbage_error_count": len(g_errs),
        "pass": True,
    }
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        errs = list(validator.iter_errors(doc))
        if errs:
            return fail(f"artifact schema errors {errs[0].message}")
        dumped = json.dumps(doc)
        if "SUCCESS:CNL-0065" not in dumped:
            return fail("sentinel absent in artifact")
        q = doc.get("quantification") or {}
        if "independent_mean_abs_dp_indep" not in q:
            return fail("artifact missing independent_mean_abs_dp_indep")
        claimed = float(q["independent_mean_abs_dp_indep"])
        if claimed > SILENT_MAX:
            return fail(f"artifact independent dp not silent {claimed}")
        payload["artifact_schema_ok"] = True

    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "negative_control=SILENT_on_tau0 independent_mean_abs_dp_indep="
        f"{indep['mean_abs_dp_indep']:.3e} tau0_inflation={inf0} "
        f"fired_on_correlated=True correlated_mean_abs_dp_indep="
        f"{corr['mean_abs_dp_indep']:.6f} schema_garbage_errors={len(g_errs)}"
    )
    print(
        "NEGATIVE-CONTROL verbatim: the overconfidence check is SILENT on "
        "independent seats (tau=0), where indep Bayes matches the joint "
        "posterior; it FIRES on the correlated same-vendor fixture."
    )
    print("SUCCESS:CNL-0065-probe2 negative control both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
