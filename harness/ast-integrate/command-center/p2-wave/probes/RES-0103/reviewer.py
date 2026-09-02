"""Adversarial reviewer: recompute Chow + E3 gate; default REFUTED."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chow as C  # noqa: E402
import fixtures as F  # noqa: E402
import grader as G  # noqa: E402

ADDED_MODE = {
    "id": "FM-COST-RATIO-UNSTATED",
    "title": "Threshold named without a cost ratio",
    "author_missed": False,
    "description": (
        "A confidence cutoff with no C_wrong:C_miss is not a recommendation; "
        "the Bayes reject option is undefined until those two costs are stated. "
        "Inverting the ratio is the control that the cutoff is load-bearing."
    ),
}


def review(doc: dict) -> dict:
    scores, correct = F.calibrated_items()
    rec = doc["threshold_recommendation"]
    cw = float(rec["assumed_cost_wrong"])
    cm = float(rec["assumed_cost_miss"])
    tau = float(rec["tau"])
    want = C.chow_tau(cw, cm)
    tau_ok = abs(tau - want) < 1e-9

    icw = float(rec["inverted_cost_wrong"])
    icm = float(rec["inverted_cost_miss"])
    itau = float(rec["inverted_tau"])
    invert_pair = C.invert_ratio(cw, cm)
    invert_ok = (icw, icm) == invert_pair and abs(itau - C.chow_tau(icw, icm)) < 1e-9
    invert_moves = abs(itau - tau) > 1e-9

    worse = C.abstention_strictly_worse(scores, correct, icw, icm)
    cheaper_on_assumed = C.expected_cost(
        scores, correct, tau, cw, cm
    ) < C.always_answer_cost(correct, cw)

    e3_promoted = []
    for m in doc.get("mechanisms") or []:
        if G.grade_mechanism(m) == "E3" and (
            m.get("promoted") is True
            or m.get("id") in (doc.get("promoted_mechanism_ids") or [])
        ):
            e3_promoted.append(m.get("id"))

    transfer = str(doc.get("transfer_verdict") or "").upper()
    transfer_not_confirmed = transfer in {
        "REFUTED",
        "NOT-ESTABLISHED",
        "NOT_ESTABLISHED",
        "UNSETTLED",
    }

    ok = (
        tau_ok
        and invert_ok
        and invert_moves
        and worse
        and cheaper_on_assumed
        and not e3_promoted
        and transfer_not_confirmed
        and str(doc.get("state") or "") == "SUCCESS"
    )
    return {
        "reviewer_id": "RES-0103-mechanical-cost-ratio-reviewer",
        "independent": True,
        "scope_not_agreement": True,
        "defaults_to_refuted": True,
        "verdict": "PASS" if ok else "FAIL",
        "tau_matches_chow": tau_ok,
        "inverted_ratio_moves_threshold": invert_moves,
        "inverted_tau_matches_chow": invert_ok,
        "abstention_strictly_worse_on_inverted": worse,
        "assumed_ratio_beats_always_answer": cheaper_on_assumed,
        "e3_promoted": e3_promoted,
        "transfer_verdict": transfer,
        "added_failure_mode": ADDED_MODE,
        "rerun": True,
    }
