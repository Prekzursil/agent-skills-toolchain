#!/usr/bin/env python3
"""Probe 1: Brier/log/bins, always-95% separation, resolution honesty, hand fixture.

Re-runs the scoring pipeline on the scripted corpus and checks the live receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from calibration import full_report  # noqa: E402
from corpus import ALWAYS95, HAND_BRIER, SEED  # noqa: E402
from inspect_simulate import inspect_simulator  # noqa: E402

RECEIPT = REPO / "command-center/receipts/TST-0287.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0287-probe1 {msg}")
    return 1


def main() -> int:
    rep = full_report()
    scored = rep["scored"]
    n_res = int(rep["n_resolved"])
    n_un = int(rep["n_unresolved"])
    print(f"n_forecasts={rep['n_forecasts']} n_resolved={n_res} n_unresolved={n_un}")
    print(f"brier={scored['brier']:.12f} log_score={scored['log_score']:.12f}")
    print(
        f"brier_always95={scored['brier_always95']:.12f} "
        f"log_score_always95={scored['log_score_always95']:.12f} "
        f"separates={scored['control_separates']}"
    )
    for b in scored["reliability_discrete"]:
        print(
            f"bin stated_p={b['stated_p']:.2f} n={b['n']} "
            f"observed={b['observed_accuracy']:.4f} gap={b['abs_gap']:.4f}"
        )
    bin80 = scored["bin80"]
    print(
        f"bin80 n={bin80['n']} correct={bin80['n_correct']} "
        f"obs={bin80['observed_accuracy']:.4f} "
        f"wilson=[{bin80['wilson_lo']:.6f},{bin80['wilson_hi']:.6f}]"
    )

    if n_res != 50:
        return fail(f"expected 50 resolved, got {n_res}")
    if n_un != 6:
        return fail(f"expected 6 unresolved, got {n_un}")
    if any("y" in u for u in rep["unresolved"]):
        return fail("unresolved rows carry an outcome y")
    unresolved_ids = {u["forecast_id"] for u in rep["unresolved"]}
    resolved_ids = {r["forecast_id"] for r in rep["resolved"]}
    if unresolved_ids & resolved_ids:
        return fail("unresolved id also in resolved")
    if abs(bin80["observed_accuracy"] - 0.8) > 1e-12 or int(bin80["n"]) != 10:
        return fail(f"0.80 bin not 8/10: {bin80}")
    if abs(scored["brier"] - 0.19) > 1e-12:
        return fail(f"brier expected 0.19 got {scored['brier']}")
    if abs(scored["brier_always95"] - 0.2725) > 1e-12:
        return fail(f"always95 brier expected 0.2725 got {scored['brier_always95']}")
    if not scored["control_separates"]:
        return fail("always-95% did not separate from the calibrated arm")
    if scored["brier_always95"] <= scored["brier"]:
        return fail("always-95% Brier is not worse")
    if scored["log_score_always95"] >= scored["log_score"]:
        return fail("always-95% log score is not worse")

    hon = rep["honesty"]
    print(
        f"honesty honest_n={hon['honest_n']} mutated_n={hon['mutated_n']} "
        f"n_inflated={hon['n_inflated']} brier_changed={hon['brier_changed']}"
    )
    if not hon["n_inflated"] or not hon["brier_changed"]:
        return fail("honesty mutation did not inflate n and change Brier")
    if hon["honest_n"] != n_res or hon["mutated_n"] != n_res + n_un:
        return fail("honesty mutation counts mismatch")

    hb = float(rep["hand_brier"])
    print(f"hand_brier={hb:.12f} expected={HAND_BRIER}")
    if abs(hb - HAND_BRIER) > 1e-12:
        return fail("hand-computed Brier fixture mismatch")

    sim = inspect_simulator(seed=SEED)
    print(
        f"simulate present={sim['present']} ran={sim['ran']} status={sim['status']} "
        f"n_ballots={sim['n_ballots']} keys={sim['ballot_keys']} "
        f"has_stated_p={sim['has_stated_p']} usable={sim['usable_as_forecast_table']}"
    )
    if sim.get("error"):
        return fail(f"simulate inspect error {sim['error']}")
    if sim.get("present") and (not sim.get("ran") or sim.get("status") != "complete"):
        return fail(f"simulate.py did not complete: {sim}")
    if sim.get("usable_as_forecast_table"):
        return fail("simulate.py unexpectedly emitted stated_p; scoring path must change")

    if not RECEIPT.is_file():
        return fail(f"receipt missing {RECEIPT}")
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt self-declared {doc.get('state')}")
    text = RECEIPT.read_text(encoding="utf-8")
    if "SUCCESS:TST-0287" not in text:
        return fail("sentinel absent from receipt")
    scores = doc.get("scores") or {}
    if abs(float(scores.get("brier")) - scored["brier"]) > 1e-9:
        return fail("receipt brier != live brier")
    if abs(float(scores.get("log_score")) - scored["log_score"]) > 1e-9:
        return fail("receipt log_score != live log_score")
    if int(scores.get("n_resolved")) != n_res:
        return fail("receipt n_resolved mismatch")
    if int(scores.get("n_unresolved")) != n_un:
        return fail("receipt n_unresolved mismatch")
    ctrl = doc.get("reference_control") or {}
    if ctrl.get("metric_separates") is not True:
        return fail("receipt control.metric_separates is not true")
    if abs(float(ctrl.get("stated_p")) - ALWAYS95) > 1e-12:
        return fail("receipt control p != 0.95")
    honesty = doc.get("resolution_honesty") or {}
    if honesty.get("unresolved_scored_as_correct") is not False:
        return fail("receipt claims unresolved were scored as correct")
    if int(honesty.get("unresolved_counted") or -1) != n_un:
        return fail("receipt unresolved_counted mismatch")
    bins = (doc.get("reliability_diagram") or {}).get("discrete_stated_p_bins") or []
    if len(bins) != 5:
        return fail(f"expected 5 discrete bins, got {len(bins)}")
    for b in bins:
        if int(b.get("n") or 0) < 1:
            return fail(f"bin without counts: {b}")
    claim = str(doc.get("claim") or "")
    if n_res < 30 and "fewer than 30" not in claim.lower():
        return fail("n<30 but claim omitted the required small-sample sentence")
    if "unresolved" not in claim.lower():
        return fail("claim does not mention unresolved exclusion")
    rec_sim = (doc.get("corpus") or {}).get("simulate") or {}
    if bool(rec_sim.get("present")) != bool(sim.get("present")):
        return fail("receipt simulate.present != live inspect")
    if sim.get("present") and "simulate.py is absent" in claim:
        return fail("claim says simulate.py is absent but the file is present")
    if sim.get("present") and rec_sim.get("usable_as_forecast_table") is True:
        return fail("receipt claims simulate.py is a forecast table")

    print("SUCCESS:TST-0287-probe1 scores bins honesty control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
