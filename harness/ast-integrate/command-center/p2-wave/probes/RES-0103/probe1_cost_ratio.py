#!/usr/bin/env python3
"""Probe 1: cost-ratio threshold, inversion, abstention-worse control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import chow as C  # noqa: E402
import fixtures as F  # noqa: E402

ART = REPO / "command-center/research/RES-0103.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0103-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rec = doc.get("threshold_recommendation") or {}
    try:
        cw = float(rec["assumed_cost_wrong"])
        cm = float(rec["assumed_cost_miss"])
        tau = float(rec["tau"])
        icw = float(rec["inverted_cost_wrong"])
        icm = float(rec["inverted_cost_miss"])
        itau = float(rec["inverted_tau"])
    except (KeyError, TypeError, ValueError) as exc:
        return fail(f"non-numeric cost ratio: {exc}")

    want = C.chow_tau(cw, cm)
    print(f"assumed_ratio={cw:g}:{cm:g} chow_tau={want:.4f} recorded_tau={tau:.4f}")
    if abs(tau - want) > 1e-9:
        return fail(f"tau {tau} != Chow {want}")

    inv = C.invert_ratio(cw, cm)
    print(f"inverted_ratio={icw:g}:{icm:g} recorded={inv}")
    if (icw, icm) != inv:
        return fail("inverted costs are not the swapped pair")
    iwant = C.chow_tau(icw, icm)
    print(f"inverted_chow_tau={iwant:.4f} recorded={itau:.4f}")
    if abs(itau - iwant) > 1e-9:
        return fail(f"inverted tau {itau} != Chow {iwant}")
    if abs(itau - tau) < 1e-9:
        return fail("inverted ratio did not move the threshold")

    scores, correct = F.calibrated_items()
    always = C.always_answer_cost(correct, cw)
    chow_c = C.expected_cost(scores, correct, tau, cw, cm)
    print(f"fixture always_answer={always:g} chow_cost={chow_c:g}")
    if chow_c >= always:
        return fail("stated ratio: Chow cutoff is not cheaper than always answering")

    emp_tau, emp_cost = C.grid_best_tau(scores, correct, cw, cm)
    print(f"empirical_best_tau={emp_tau:.4f} empirical_cost={emp_cost:g}")
    if abs(emp_cost - chow_c) > 1e-9:
        return fail(
            f"Chow tau is not a cost minimizer: chow={chow_c} best={emp_cost}"
        )

    worse = C.abstention_strictly_worse(scores, correct, icw, icm)
    inv_always = C.always_answer_cost(correct, icw)
    inv_075 = C.expected_cost(scores, correct, 0.75, icw, icm)
    print(
        f"control inverted always={inv_always:g} tau075={inv_075:g} "
        f"abstention_strictly_worse={worse}"
    )
    if not worse:
        return fail("control: abstention not strictly worse under inverted ratio")
    if inv_075 <= inv_always:
        return fail("control: tau=0.75 was not more expensive after inversion")
    if iwant != 0.0:
        return fail("control: inverted Chow tau must be 0 (always answer)")

    text = ART.read_text(encoding="utf-8")
    needle = (
        "SUCCESS:RES-0103 in the receipt AND a threshold recommendation "
        "with an explicit cost-ratio assumption and an inverted-ratio sensitivity"
    )
    if needle not in text:
        return fail("completion sentinel absent from artifact")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    print("SUCCESS:RES-0103-probe1 cost-ratio inversion and abstention-worse control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
