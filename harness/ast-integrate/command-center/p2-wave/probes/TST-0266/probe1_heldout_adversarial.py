#!/usr/bin/env python3
"""Probe 1: live held-out kappa + adversarial distinct-recall.

Re-runs the novelty runtime on the published gold set with frozen thresholds
and compares the statistic to the catalog receipt. Does not trust the stored
kappa field without recomputing it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from calibrate import adversarial_metrics, slice_metrics  # noqa: E402
from gold import load_gold  # noqa: E402
from kappa import cohen_kappa  # noqa: E402
from novelty_runtime import KAPPA_FLOOR, classify_pair  # noqa: E402

ART = REPO / "command-center/receipts/TST-0266.json"
THRESH = HERE / "fixtures" / "thresholds.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0266-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if "SUCCESS:TST-0266" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if not THRESH.is_file():
        return fail("frozen thresholds missing")
    thr = json.loads(THRESH.read_text(encoding="utf-8"))
    t_dup, t_var = float(thr["t_dup"]), float(thr["t_var"])
    if str(thr.get("tuned_on") or "") != "tune":
        return fail("thresholds not marked as tune-only")
    gold = load_gold()
    if gold["kappa_floor_preregistered"] != KAPPA_FLOOR:
        return fail("floor drift")
    if not gold.get("kappa_floor_recorded_before_any_score"):
        return fail("floor not pre-registered")
    rows = gold["pairs"]
    held = [r for r in rows if r["split"] == "heldout"]
    tune = [r for r in rows if r["split"] == "tune"]
    if len(held) != 30 or len(tune) != 30:
        return fail(f"split sizes tune={len(tune)} held={len(held)}")
    live = slice_metrics(held, t_dup, t_var, seed=266)
    rec_k = float((doc.get("heldout") or {}).get("kappa"))
    if abs(live["kappa"] - rec_k) > 1e-12:
        return fail(f"heldout kappa live={live['kappa']} receipt={rec_k}")
    rec_n = int((doc.get("heldout") or {}).get("n") or 0)
    if rec_n != live["n"]:
        return fail(f"heldout n live={live['n']} receipt={rec_n}")
    rec_ci = (doc.get("heldout") or {}).get("ci") or {}
    if abs(float(rec_ci.get("ci_low")) - live["ci"]["ci_low"]) > 1e-12:
        return fail("ci_low mismatch")
    if abs(float(rec_ci.get("ci_high")) - live["ci"]["ci_high"]) > 1e-12:
        return fail("ci_high mismatch")
    # Tuning half must not be the reported kappa half.
    tune_live = [classify_pair(r["idea_a"], r["idea_b"], t_dup, t_var) for r in tune]
    tune_k = cohen_kappa([r["label"] for r in tune], tune_live)
    if abs(tune_k - live["kappa"]) < 1e-15 and set(r["id"] for r in tune) == set(
        r["id"] for r in held
    ):
        return fail("tune and heldout are the same set")
    adv = adversarial_metrics(held, t_dup, t_var)
    rec_adv = doc.get("adversarial_heldout") or {}
    if abs(float(rec_adv.get("recall_distinct")) - adv["recall_distinct"]) > 1e-12:
        return fail("adversarial recall mismatch")
    if adv["n"] < 1:
        return fail("no held-out adversarial pairs")
    if adv["recall_distinct"] < 1.0:
        return fail(f"adversarial distinct-recall {adv['recall_distinct']}")
    if live["kappa"] < KAPPA_FLOOR:
        print(
            f"note: held-out kappa {live['kappa']} is below floor {KAPPA_FLOOR}; "
            "novelty must be advisory"
        )
    print(
        json.dumps(
            {
                "heldout_n": live["n"],
                "heldout_kappa": live["kappa"],
                "ci_low": live["ci"]["ci_low"],
                "ci_high": live["ci"]["ci_high"],
                "tune_kappa_not_reported": tune_k,
                "adv_n": adv["n"],
                "adv_recall_distinct": adv["recall_distinct"],
                "t_dup": t_dup,
                "t_var": t_var,
            },
            sort_keys=True,
        )
    )
    print(
        f"heldout_kappa={live['kappa']:.6f} ci=[{live['ci']['ci_low']:.6f},"
        f"{live['ci']['ci_high']:.6f}] adv_recall={adv['recall_distinct']}"
    )
    print("SUCCESS:TST-0266-probe1 held-out kappa and adversarial slice reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
