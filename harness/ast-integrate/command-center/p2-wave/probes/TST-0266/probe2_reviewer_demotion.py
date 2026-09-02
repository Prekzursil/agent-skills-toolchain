#!/usr/bin/env python3
"""Probe 2: statistics reviewer + demotion rule.

Mechanically independent of probe 1: does not call classify_pair. Recomputes
Cohen's kappa and the bootstrap interval from the published per-case table,
then executes the seeded below-floor scorer against the stopping-rule gate.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from novelty_runtime import (  # noqa: E402
    KAPPA_FLOOR,
    apply_novelty_to_stop_expression,
    seeded_broken_predictions,
    stopping_rule_from_kappa,
)

ART = REPO / "command-center/receipts/TST-0266.json"
LABELS = ("duplicate", "variant", "distinct")
BOOTSTRAP_SEED = 266
BOOTSTRAP_N = 2000


def fail(msg: str) -> int:
    print(f"FAILED:TST-0266-probe2 {msg}")
    return 1


def reviewer_kappa(y_true: list[str], y_pred: list[str]) -> dict:
    """Independent 3-class kappa; not imported from kappa.py."""
    idx = {lab: i for i, lab in enumerate(LABELS)}
    n = len(y_true)
    if n == 0 or n != len(y_pred):
        raise ValueError("empty or misaligned series")
    matrix = [[0, 0, 0] for _ in range(3)]
    for t, p in zip(y_true, y_pred):
        matrix[idx[t]][idx[p]] += 1
    observed = sum(matrix[i][i] for i in range(3)) / n
    row = [sum(matrix[i]) for i in range(3)]
    col = [sum(matrix[r][c] for r in range(3)) for c in range(3)]
    expected = sum((row[i] / n) * (col[i] / n) for i in range(3))
    if expected >= 1.0:
        kap = 1.0 if observed >= 1.0 else 0.0
    else:
        kap = (observed - expected) / (1.0 - expected)
    return {"n": n, "kappa": kap, "matrix": matrix, "observed": observed, "expected": expected}


def reviewer_bootstrap_ci(y_true: list[str], y_pred: list[str]) -> dict:
    n = len(y_true)
    stats: list[float] = []
    state = BOOTSTRAP_SEED & 0xFFFFFFFF
    for _ in range(BOOTSTRAP_N):
        idx: list[int] = []
        for _j in range(n):
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            idx.append(state % n)
        yt = [y_true[i] for i in idx]
        yp = [y_pred[i] for i in idx]
        stats.append(reviewer_kappa(yt, yp)["kappa"])
    stats.sort()
    lo_i = max(0, min(BOOTSTRAP_N - 1, int(math.floor(0.025 * BOOTSTRAP_N))))
    hi_i = max(0, min(BOOTSTRAP_N - 1, int(math.ceil(0.975 * BOOTSTRAP_N) - 1)))
    return {"ci_low": stats[lo_i], "ci_high": stats[hi_i], "lo_index": lo_i, "hi_index": hi_i}


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0266" not in json.dumps(doc):
        return fail("sentinel-absent")
    gold = doc.get("gold_set") or {}
    pairs = gold.get("pairs") or []
    if len(pairs) != 60:
        return fail(f"published gold set size {len(pairs)} != 60")
    if gold.get("kappa_floor_preregistered") != KAPPA_FLOOR:
        return fail("published floor does not match runtime constant")
    if not gold.get("kappa_floor_recorded_before_any_score"):
        return fail("floor not attested as pre-registered")
    cases = ((doc.get("heldout") or {}).get("per_case")) or []
    if len(cases) != 30:
        return fail(f"held-out per_case n={len(cases)}")
    y_true = [c["label"] for c in cases]
    y_pred = [c["predicted"] for c in cases]
    if any(x not in LABELS for x in y_true + y_pred):
        return fail("non-canonical label in per_case")
    got = reviewer_kappa(y_true, y_pred)
    rec_k = float((doc.get("heldout") or {}).get("kappa"))
    if abs(got["kappa"] - rec_k) > 1e-12:
        return fail(f"recomputed kappa {got['kappa']} != reported {rec_k}")
    boot = reviewer_bootstrap_ci(y_true, y_pred)
    rec_ci = (doc.get("heldout") or {}).get("ci") or {}
    if abs(boot["ci_low"] - float(rec_ci.get("ci_low"))) > 1e-12:
        return fail("reviewer ci_low mismatch")
    if abs(boot["ci_high"] - float(rec_ci.get("ci_high"))) > 1e-12:
        return fail("reviewer ci_high mismatch")

    # Wiring control: shuffling predictions must move kappa.
    shuffled = seeded_broken_predictions(y_pred, seed=99)
    mut = reviewer_kappa(y_true, shuffled)
    if abs(mut["kappa"] - got["kappa"]) < 1e-9:
        return fail("shuffled predictions left kappa unchanged; statistic not wired")

    broken = seeded_broken_predictions(y_true, seed=26601)
    broken_k = reviewer_kappa(y_true, broken)["kappa"]
    if broken_k >= KAPPA_FLOOR:
        return fail(f"seeded scorer kappa {broken_k} not below floor")
    rec_broken = ((doc.get("demotion") or {}).get("seeded_below_floor") or {}).get("kappa")
    if rec_broken is None or abs(float(rec_broken) - broken_k) > 1e-12:
        return fail("seeded-below-floor kappa not reproduced")
    gate = stopping_rule_from_kappa(broken_k, KAPPA_FLOOR)
    stop = apply_novelty_to_stop_expression(
        {"predicate": "unique_ideas >= 100 AND novelty_score >= 0.8", "uses_novelty_score": True},
        broken_k,
        KAPPA_FLOOR,
    )
    if gate["may_gate_stopping_rule"] is not False:
        return fail("demotion did not refuse the stopping-rule gate")
    if stop["accepted"] is not False:
        return fail("stop expression with novelty was accepted below floor")
    if gate["novelty_role"] != "advisory":
        return fail("below-floor role is not advisory")

    perfect = stopping_rule_from_kappa(1.0, KAPPA_FLOOR)
    perfect_stop = apply_novelty_to_stop_expression(
        {"predicate": "unique_ideas >= 100 AND novelty_score >= 0.8", "uses_novelty_score": True},
        1.0,
        KAPPA_FLOOR,
    )
    if perfect["may_gate_stopping_rule"] is not True or perfect_stop["accepted"] is not True:
        return fail("demotion fired on perfect-agreement control")

    live_k = rec_k
    live_gate = stopping_rule_from_kappa(live_k, KAPPA_FLOOR)
    rec_live = ((doc.get("demotion") or {}).get("live") or {}).get("gate") or {}
    if bool(rec_live.get("may_gate_stopping_rule")) != live_gate["may_gate_stopping_rule"]:
        return fail("live demotion flag mismatch")

    print(
        json.dumps(
            {
                "reviewer_kappa": got["kappa"],
                "reviewer_n": got["n"],
                "reviewer_ci": [boot["ci_low"], boot["ci_high"]],
                "gold_set_size": len(pairs),
                "shuffled_kappa": mut["kappa"],
                "seeded_below_floor_kappa": broken_k,
                "demotion_fired": True,
                "perfect_control_silent": True,
                "live_may_gate": live_gate["may_gate_stopping_rule"],
                "live_role": live_gate["novelty_role"],
            },
            sort_keys=True,
        )
    )
    print(
        f"reviewer_kappa={got['kappa']:.6f} n={got['n']} "
        f"ci=[{boot['ci_low']:.6f},{boot['ci_high']:.6f}] "
        f"demotion_fired=True"
    )
    print("SUCCESS:TST-0266-probe2 reviewer reproduced effect size and demotion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
