#!/usr/bin/env python3
"""Probe 2: same-vendor noise floor + independent recompute + naive-nominal reject.

Re-derives phi and effective seats from the raw per-item error vectors (not
from the author's summary object). Compares cross-vendor correlation to two
runs of the SAME vendor. Rejects a correlator that always reports 2 seats.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.council.calibration.vendor_error_correlation import (  # noqa: E402
    errors_of,
    naive_nominal_seats,
    run_independence_experiment,
)
import naive_nominal as NN  # noqa: E402


def phi_from_vectors(ea: list[bool], eb: list[bool]) -> float | None:
    """Reviewer-side phi. Count form, not the library summarize_pair path."""
    n_bb = n_br = n_rb = n_rr = 0
    for a, b in zip(ea, eb):
        if a and b:
            n_bb += 1
        elif a and not b:
            n_br += 1
        elif (not a) and b:
            n_rb += 1
        else:
            n_rr += 1
    n1 = n_bb + n_br
    n0 = n_rb + n_rr
    m1 = n_bb + n_rb
    m0 = n_br + n_rr
    den = math.sqrt(n1 * n0 * m1 * m0)
    if den == 0:
        return None
    return ((n_bb * n_rr) - (n_br * n_rb)) / den


def seats_from_phi(phi: float | None) -> float | None:
    if phi is None:
        return None
    rho = max(-0.999999, min(0.999999, phi))
    return 2.0 / (1.0 + rho)


def main() -> int:
    exp = run_independence_experiment(seed=292)
    rows = exp["rows"]
    ea = errors_of(rows["claude_r1"])
    eb_indep = errors_of(rows["codex_independent"])
    eb_clone = errors_of(rows["codex_clone"])
    ea2 = errors_of(rows["claude_r2"])

    phi_indep = phi_from_vectors(ea, eb_indep)
    phi_clone = phi_from_vectors(ea, eb_clone)
    phi_floor = phi_from_vectors(ea, ea2)
    seats_indep = seats_from_phi(phi_indep)
    seats_clone = seats_from_phi(phi_clone)
    seats_floor = seats_from_phi(phi_floor)

    lib_indep = exp["independent_pair"]["phi"]
    lib_clone = exp["cloned_pair"]["phi"]
    lib_floor = exp["same_vendor_baseline"]["phi"]

    recompute_ok = (
        phi_indep is not None
        and phi_clone is not None
        and phi_floor is not None
        and abs(phi_indep - lib_indep) < 1e-12
        and abs(phi_clone - lib_clone) < 1e-12
        and abs(phi_floor - lib_floor) < 1e-12
    )

    naive_lib = naive_nominal_seats(rows["claude_r1"], rows["codex_clone"])
    naive_alt = NN.always_two_seats(rows["claude_r1"], rows["codex_clone"])
    naive_fires = (
        naive_lib["effective_seats"] == 2.0
        and naive_alt["effective_seats"] == 2.0
        and seats_clone is not None
        and seats_clone < 1.30
        and naive_alt["effective_seats"] - seats_clone > 0.5
    )

    floor_above_independent = (
        phi_floor is not None
        and phi_indep is not None
        and phi_floor - phi_indep > 0.25
    )
    clone_near_floor = (
        phi_clone is not None
        and phi_floor is not None
        and abs(phi_clone - phi_floor) < 0.20
    )
    parity_negative = not exp["prompt_parity_negative"]["prompt_parity"]["ok"]

    report = {
        "probe": "probe2-same-vendor-baseline",
        "unit_id": "TST-0292",
        "reviewer_recompute": {
            "phi_independent": phi_indep,
            "phi_cloned": phi_clone,
            "phi_same_vendor": phi_floor,
            "seats_independent": seats_indep,
            "seats_cloned": seats_clone,
            "seats_same_vendor": seats_floor,
            "matches_library": recompute_ok,
        },
        "noise_floor": {
            "same_vendor_phi": phi_floor,
            "independent_phi": phi_indep,
            "cloned_phi": phi_clone,
            "independent_below_floor": floor_above_independent,
            "cloned_near_floor": clone_near_floor,
        },
        "naive_nominal": {
            "library_seats": naive_lib["effective_seats"],
            "module_seats": naive_alt["effective_seats"],
            "honest_cloned_seats": seats_clone,
            "rejected": naive_fires,
        },
        "prompt_parity_negative_fired": parity_negative,
        "n_scored": len(ea),
        "live_arm": exp["live_substrate"]["live_arm"],
        "token_spend": exp["independent_pair"]["token_spend"],
    }
    print(json.dumps(report, sort_keys=True, default=str))
    print(
        "recompute_ok={ok} floor={fl:.4f} indep={ip:.4f} clone={cp:.4f} "
        "naive_rejected={nr} parity_neg={pn}".format(
            ok=recompute_ok,
            fl=phi_floor or -1,
            ip=phi_indep or -1,
            cp=phi_clone or -1,
            nr=naive_fires,
            pn=parity_negative,
        )
    )
    failures: list[str] = []
    if len(ea) < 100:
        failures.append("need-100-plus-items")
    if not recompute_ok:
        failures.append("reviewer-phi-mismatch")
    if not floor_above_independent:
        failures.append("independent-not-below-same-vendor-floor")
    if not clone_near_floor:
        failures.append("cloned-not-at-same-vendor-floor")
    if not naive_fires:
        failures.append("naive-nominal-not-rejected")
    if not parity_negative:
        failures.append("prompt-parity-negative-silent")
    if failures:
        print("FAILED:TST-0292-probe2 " + ",".join(failures))
        return 1
    print(
        "SUCCESS:TST-0292-probe2 same-vendor floor compared; reviewer "
        "recomputed phi; naive nominal seats rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
