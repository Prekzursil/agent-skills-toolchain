#!/usr/bin/env python3
"""Probe 2: calibration simulation with known ground truth.

Four cells, same seed: correlated vs independent panels, naive vs
discounted pooling. Correlated naive must have worse MSE-to-truth and a
higher near-certain rate than correlated discounted. A fully-correlated
panel must not yield a near-certain discounted credence.

Negative control: forcing discount=False on the correlated cell makes
the near-certain-rate check FAIL (the property the unit exists to catch).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.vote.bayes import (  # noqa: E402
    SIM_K_OBS,
    SIM_N_EXPERTS,
    SIM_N_TRIALS,
    SIM_P_TRUE,
    SIM_SEED,
    run_calibration_simulation,
)

ART = REPO / "command-center/receipts/IMP-0305.json"
SENTINEL = "SUCCESS:IMP-0305"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0305-probe2 {msg}")
    return 1


def _num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def main() -> int:
    sim = run_calibration_simulation()
    cn = sim["correlated_naive"]
    cd = sim["correlated_discounted"]
    inn = sim["independent_naive"]
    ind = sim["independent_discounted"]

    payload = {
        "probe": "probe2-calibration-sim",
        "seed": sim["seed"],
        "p_true": sim["p_true"],
        "n_trials": sim["n_trials"],
        "correlated_naive_mse": cn["mse_to_truth"],
        "correlated_discounted_mse": cd["mse_to_truth"],
        "correlated_naive_brier": cn["brier"],
        "correlated_discounted_brier": cd["brier"],
        "correlated_naive_ece": cn["ece"],
        "correlated_discounted_ece": cd["ece"],
        "correlated_naive_near_certain_rate": cn["near_certain_rate"],
        "correlated_discounted_near_certain_rate": cd["near_certain_rate"],
        "independent_naive_mse": inn["mse_to_truth"],
        "independent_discounted_mse": ind["mse_to_truth"],
        "independent_rho": ind["mean_rho"],
        "correlated_rho": cd["mean_rho"],
        "mse_naive_worse": sim["correlated_mse_naive_worse"],
        "brier_naive_worse": sim["correlated_brier_naive_worse"],
    }
    print(json.dumps(payload, indent=1, sort_keys=True))

    for key in (
        "mse_to_truth",
        "brier",
        "ece",
        "near_certain_rate",
        "mean_pooled",
    ):
        if not _num(cn[key]) or not _num(cd[key]):
            return _fail(f"{key} is not a number")

    if sim["seed"] != SIM_SEED or sim["p_true"] != SIM_P_TRUE:
        return _fail("simulation hyperparameters drifted")
    if sim["n_trials"] != SIM_N_TRIALS or sim["n_experts"] != SIM_N_EXPERTS:
        return _fail("simulation size drifted")
    if sim["k_obs"] != SIM_K_OBS:
        return _fail("k_obs drifted")

    if cd["mean_rho"] != 1.0:
        return _fail(f"correlated roster rho={cd['mean_rho']} not 1")
    if ind["mean_rho"] != 0.0:
        return _fail(f"independent roster rho={ind['mean_rho']} not 0")
    if abs(inn["mse_to_truth"] - ind["mse_to_truth"]) > 1e-12:
        return _fail("rho=0 independent cells diverged")
    if abs(inn["near_certain_rate"] - ind["near_certain_rate"]) > 1e-12:
        return _fail("rho=0 independent near-certain rates diverged")

    if not sim["correlated_mse_naive_worse"]:
        return _fail(
            f"correlated naive MSE {cn['mse_to_truth']} was not worse than "
            f"discounted {cd['mse_to_truth']}"
        )
    if not sim["correlated_brier_naive_worse"]:
        return _fail("correlated naive Brier was not worse than discounted")
    if cn["near_certain_rate"] <= 0.0:
        return _fail("correlated naive never went near-certain")
    if cd["near_certain_rate"] != 0.0:
        return _fail(
            f"correlated discounted near-certain rate={cd['near_certain_rate']} "
            "(fully-correlated panel must not be near-certain)"
        )
    if cd["mse_to_truth"] >= cn["mse_to_truth"]:
        return _fail("discount did not reduce MSE to known p_true")

    # Negative control: the naive correlated cell IS the broken state.
    # If we required "near-certain rate == 0" of THAT cell, the check fails.
    naive_would_pass_neg = cn["near_certain_rate"] == 0.0
    disc_passes_neg = cd["near_certain_rate"] == 0.0
    print(
        f"negative_control_naive_fails_not_near_certain={not naive_would_pass_neg} "
        f"discounted_passes={disc_passes_neg}"
    )
    if naive_would_pass_neg:
        return _fail("negative control: naive correlated was already not near-certain")
    if not disc_passes_neg:
        return _fail("negative control: discounted correlated was near-certain")

    if not ART.is_file():
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return _fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")
    rec = doc.get("simulation") or {}
    for field, live in (
        ("correlated_naive_mse", cn["mse_to_truth"]),
        ("correlated_discounted_mse", cd["mse_to_truth"]),
        ("correlated_naive_brier", cn["brier"]),
        ("correlated_discounted_brier", cd["brier"]),
        ("correlated_naive_near_certain_rate", cn["near_certain_rate"]),
        ("correlated_discounted_near_certain_rate", cd["near_certain_rate"]),
        ("p_true", sim["p_true"]),
    ):
        got = rec.get(field)
        if not _num(got):
            return _fail(f"receipt simulation.{field} is not a number")
        if abs(float(got) - float(live)) > 1e-12:
            return _fail(f"receipt simulation.{field} stale {got} vs live {live}")
    if rec.get("seed") != SIM_SEED:
        return _fail("receipt simulation seed mismatch")

    reviewer = doc.get("reviewer") or {}
    if str(reviewer.get("verdict") or doc.get("reviewer_verdict") or "").upper() != "PASS":
        return _fail("reviewer_verdict is not PASS")

    print(
        "SUCCESS:IMP-0305-probe2 calibration-sim "
        f"mse_naive={cn['mse_to_truth']:.6f} mse_disc={cd['mse_to_truth']:.6f} "
        f"near_naive={cn['near_certain_rate']:.3f} near_disc={cd['near_certain_rate']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
