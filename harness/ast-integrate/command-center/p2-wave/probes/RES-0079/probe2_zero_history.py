#!/usr/bin/env python3
"""Probe 2: control — which method is usable TODAY with zero labelled history.

Live DGP (seed 79): equal-weight linear and log pools are defined at n_train=0;
BMA and inverse-Brier raise InsufficientHistory. After 400 labelled rows, BMA
ECE is strictly below equal-weight linear ECE.
Both-states: claiming BMA is usable at zero history is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import pool as P  # noqa: E402

ART = REPO / "command-center/research/RES-0079.json"
HISTORY_MARKERS = [
    "command-center/receipts/IMP-0352.json",
    "tools/council/participants/select_calibrated.py",
]


def fail(msg: str) -> int:
    print(f"FAILED:RES-0079-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))

    present = [rel for rel in HISTORY_MARKERS if (REPO / rel).is_file()]
    print(
        json.dumps(
            {
                "history_markers_present": present,
                "mode": "simulated-dgp-zero-history",
                "note": (
                    "Presence of unrelated receipts on this worktree is not "
                    "labelled (forecast, resolved-verdict) history for pooling."
                ),
            },
            sort_keys=True,
        )
    )

    empty_blocked = True
    try:
        P.bma_weights([])
        empty_blocked = False
    except P.InsufficientHistory:
        pass
    try:
        P.inverse_brier_weights([])
    except P.InsufficientHistory:
        pass
    else:
        empty_blocked = False
    if not empty_blocked:
        return fail("history-using weights did not block on empty history")

    ctrl = P.run_control(seed=79, n_train=400, n_test=2000)
    defined = set(ctrl["zero_history_defined"])
    blocked = ctrl["zero_history_blocked"]
    if defined != {"linear_equal", "log_equal"}:
        return fail(f"zero-history defined {sorted(defined)}")
    if blocked.get("bma") != "InsufficientHistory":
        return fail(f"bma not blocked {blocked}")
    if blocked.get("inverse_brier") != "InsufficientHistory":
        return fail(f"inverse_brier not blocked {blocked}")

    lin = ctrl["scores"]["linear_equal_zero_history"]
    logp = ctrl["scores"]["log_equal_zero_history"]
    bma = ctrl["scores"]["bma_linear_with_history"]
    if not (bma["ece"] < lin["ece"]):
        return fail(f"BMA ECE {bma['ece']} not < linear ECE {lin['ece']}")
    if not (bma["brier"] <= lin["brier"] + 1e-12):
        return fail(f"BMA Brier {bma['brier']} worse than linear {lin['brier']}")
    if not (logp["ece"] > lin["ece"]):
        return fail("expected equal-weight log ECE worse than linear on this DGP")

    zid = (doc.get("answer") or {}).get("zero_history_method_id")
    if zid != "linear-equal":
        return fail(f"artifact zero_history_method_id {zid!r}")
    if doc.get("call_sheet_grade", {}).get("verdict") != "CORROBORATED":
        return fail("call-sheet grade not corroborated")

    mutant_ok = False
    for row in doc.get("method_table") or []:
        if row.get("id") == "bayesian-bma" and row.get("usable_at_zero_history") is True:
            mutant_ok = True
    if mutant_ok:
        return fail("artifact marks BMA usable at zero history")

    live = doc.get("live_control") or {}
    art_lin = (live.get("scores") or {}).get("linear_equal_zero_history") or {}
    if abs(float(art_lin.get("brier", -1)) - lin["brier"]) > 1e-9:
        return fail("artifact live_control Brier does not match re-run")

    print("labelled_history_present", False)
    print("zero_history_defined", sorted(defined))
    print("zero_history_blocked", blocked)
    print("linear_ece", lin["ece"], "brier", lin["brier"])
    print("log_ece", logp["ece"], "brier", logp["brier"])
    print("bma_with_history_ece", bma["ece"], "brier", bma["brier"])
    print("bma_ece_strictly_below_linear", True)
    print("identified_today_method", zid)
    print("bma_usable_at_zero_history", False)
    print("SUCCESS:RES-0079-probe2 zero-history control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
