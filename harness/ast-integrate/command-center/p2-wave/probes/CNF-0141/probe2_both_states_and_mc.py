#!/usr/bin/env python3
"""Probe 2: decisive-bad stops early; borderline runs to n_max; MC error rates."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "sampling"))
import curtailed_sprt as CS  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0141.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0141-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    raw = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0141" not in raw:
        return fail("sentinel absent")
    doc = json.loads(raw)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    params = CS.default_params()

    bad = CS.CurtailedSPRT(params, severity="P2", population_n=10**6)
    st_bad = bad.consume([True] * params.n_max)
    if st_bad.decision != "REJECT_H0":
        return fail(f"decisive-bad decision={st_bad.decision} want REJECT_H0")
    if st_bad.n >= params.n_max:
        return fail(f"decisive-bad ran to n={st_bad.n}, did not stop early")
    if st_bad.truncated:
        return fail("decisive-bad should stop on SPRT bound, not truncation")

    good = CS.CurtailedSPRT(params, severity="P2", population_n=10**6)
    st_good = good.consume([False] * params.n_max)
    if st_good.decision != "ACCEPT_H0":
        return fail(f"decisive-good decision={st_good.decision} want ACCEPT_H0")
    if st_good.n >= params.n_max:
        return fail(f"decisive-good ran to n={st_good.n}, did not stop early")

    path = CS.make_continuation_path(params)
    border = CS.CurtailedSPRT(params, severity="P2", population_n=10**6)
    st_b = border.consume(path)
    if st_b.n != params.n_max or not st_b.truncated:
        return fail(
            f"borderline n={st_b.n} truncated={st_b.truncated} want n_max truncated"
        )

    rates = doc.get("error_rates") or {}
    alpha_adv = float(rates["alpha_hat"])
    beta_adv = float(rates["beta_hat"])
    tol = float(rates.get("tolerance_abs") or CS.MC_TOLERANCE_ABS)
    n_sims = 3000
    held = CS.PROBE_MC_SEED
    mc0 = CS.monte_carlo(p_true=params.p0, n_sims=n_sims, seed=held)
    mc1 = CS.monte_carlo(p_true=params.p1, n_sims=n_sims, seed=held + 1)
    d_alpha = abs(mc0["p_reject_h0"] - alpha_adv)
    d_beta = abs(mc1["p_accept_h0"] - beta_adv)
    if d_alpha > tol:
        return fail(
            f"alpha_hat live={mc0['p_reject_h0']:.4f} advertised={alpha_adv:.4f} "
            f"delta={d_alpha:.4f} > tol={tol}"
        )
    if d_beta > tol:
        return fail(
            f"beta_hat live={mc1['p_accept_h0']:.4f} advertised={beta_adv:.4f} "
            f"delta={d_beta:.4f} > tol={tol}"
        )

    oc = doc.get("operating_characteristic") or []
    if len(oc) < 6:
        return fail(f"OC curve too short: {len(oc)}")
    saving = doc.get("sample_size_saving") or {}
    if saving.get("census_shrunk") is not False:
        return fail("receipt claims census was shrunk")
    if float(saving.get("saving_frac_at_p0") or 0) <= 0:
        return fail("no sample-size saving at p0")
    if float(saving.get("saving_frac_at_p1") or 0) <= 0:
        return fail("no sample-size saving at p1")

    print(
        json.dumps(
            {
                "probe": "probe2-both-states-and-mc",
                "unit_id": "CNF-0141",
                "bad_n": st_bad.n,
                "good_n": st_good.n,
                "borderline_n": st_b.n,
                "alpha_hat_live": mc0["p_reject_h0"],
                "beta_hat_live": mc1["p_accept_h0"],
                "alpha_hat_advertised": alpha_adv,
                "beta_hat_advertised": beta_adv,
                "d_alpha": d_alpha,
                "d_beta": d_beta,
                "asn_p0": mc0["asn"],
                "asn_p1": mc1["asn"],
                "pass": True,
            }
        )
    )
    print("SUCCESS:CNF-0141-probe2 both-states and Monte-Carlo error rates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
