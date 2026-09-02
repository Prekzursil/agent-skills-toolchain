#!/usr/bin/env python3
"""Probe 2: statistics-mandate reviewer.

Independently recomputes Brier, log score, reliability bins, ΔBrier, the
bootstrap interval, and the Wilson interval from raw per-case rows.
Does not call calibration.score_resolved / calibration.brier_mean.
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RECEIPT = REPO / "command-center/receipts/TST-0287.json"
RAW = HERE / "fixtures" / "raw_cases.json"

LOG_EPS = 1e-15
ALWAYS95 = 0.95
WILSON_Z = 1.96
BOOTSTRAP_DRAWS = 2000
SEED = 287


def fail(msg: str) -> int:
    print(f"FAILED:TST-0287-probe2 {msg}")
    return 1


def clip(p: float) -> float:
    return min(1.0 - LOG_EPS, max(LOG_EPS, float(p)))


def indep_brier(pairs: list[tuple[float, int]]) -> float:
    s = 0.0
    for p, y in pairs:
        s += (p - y) * (p - y)
    return s / len(pairs)


def indep_log_score(pairs: list[tuple[float, int]]) -> float:
    s = 0.0
    for p, y in pairs:
        q = clip(p)
        s += y * math.log(q) + (1 - y) * math.log(1.0 - q)
    return s / len(pairs)


def indep_wilson(k: int, n: int, z: float = WILSON_Z) -> tuple[float, float, float]:
    phat = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    centre = (phat + z2 / (2.0 * n)) / den
    margin = z * math.sqrt((phat * (1.0 - phat) + z2 / (4.0 * n)) / n) / den
    return phat, centre - margin, centre + margin


def indep_percentile(xs: list[float], q: float) -> float:
    ys = sorted(xs)
    idx = (len(ys) - 1) * q
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return ys[lo]
    w = idx - lo
    return ys[lo] * (1.0 - w) + ys[hi] * w


def indep_bootstrap(diffs: list[float]) -> tuple[float, float, float]:
    rng = random.Random(SEED)
    n = len(diffs)
    means: list[float] = []
    for _ in range(BOOTSTRAP_DRAWS):
        acc = 0.0
        for _i in range(n):
            acc += diffs[rng.randrange(n)]
        means.append(acc / n)
    point = sum(diffs) / n
    return point, indep_percentile(means, 0.025), indep_percentile(means, 0.975)


def rebuild_pairs_from_recipe() -> list[tuple[float, int]]:
    """Second derivation of the table: same published recipe, no shared helper."""
    bands = (0.50, 0.60, 0.70, 0.80, 0.90)
    pairs: list[tuple[float, int]] = []
    for p in bands:
        n_yes = int(round(10 * p))
        for i in range(10):
            pairs.append((p, 1 if i < n_yes else 0))
    return pairs


def main() -> int:
    if not RAW.is_file():
        return fail(f"raw cases missing {RAW}")
    if not RECEIPT.is_file():
        return fail(f"receipt missing {RECEIPT}")
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    cases = raw.get("cases") or []
    file_pairs = [(float(c["stated_p"]), int(c["y"])) for c in cases]
    recipe_pairs = rebuild_pairs_from_recipe()
    if file_pairs != recipe_pairs:
        return fail("raw_cases.json does not match the published band recipe")
    if len(file_pairs) != 50:
        return fail(f"expected 50 raw cases, got {len(file_pairs)}")
    unresolved_ids = raw.get("unresolved_ids") or []
    if len(unresolved_ids) != 6:
        return fail(f"expected 6 unresolved ids, got {len(unresolved_ids)}")
    scored_ids = {c["forecast_id"] for c in cases}
    if scored_ids & set(unresolved_ids):
        return fail("unresolved id leaked into scored cases")

    brier = indep_brier(file_pairs)
    log_s = indep_log_score(file_pairs)
    brier95 = indep_brier([(ALWAYS95, y) for _, y in file_pairs])
    log95 = indep_log_score([(ALWAYS95, y) for _, y in file_pairs])
    diffs = [(ALWAYS95 - y) ** 2 - (p - y) ** 2 for p, y in file_pairs]
    delta, lo, hi = indep_bootstrap(diffs)

    by_p: dict[float, list[int]] = {}
    for p, y in file_pairs:
        by_p.setdefault(p, []).append(y)
    bins = []
    for p in sorted(by_p):
        ys = by_p[p]
        bins.append((p, len(ys), sum(ys), sum(ys) / len(ys)))

    k80 = sum(y for p, y in file_pairs if abs(p - 0.8) < 1e-12)
    n80 = sum(1 for p, _y in file_pairs if abs(p - 0.8) < 1e-12)
    phat, wlo, whi = indep_wilson(k80, n80)

    print(f"reviewer_brier={brier:.12f}")
    print(f"reviewer_log_score={log_s:.12f}")
    print(f"reviewer_brier95={brier95:.12f}")
    print(f"reviewer_delta={delta:.12f} ci=[{lo:.12f},{hi:.12f}]")
    print(f"reviewer_bin80={k80}/{n80} wilson=[{wlo:.12f},{whi:.12f}]")
    for p, n, k, obs in bins:
        print(f"reviewer_bin p={p:.2f} n={n} k={k} obs={obs:.4f}")

    scores = doc.get("scores") or {}
    ctrl = doc.get("reference_control") or {}
    boot = ctrl.get("bootstrap_95_ci") or {}
    rec_bin80 = doc.get("bin80") or {}

    if abs(float(scores["brier"]) - brier) > 1e-9:
        return fail(f"receipt brier {scores['brier']} != reviewer {brier}")
    if abs(float(scores["log_score"]) - log_s) > 1e-9:
        return fail(f"receipt log_score {scores['log_score']} != reviewer {log_s}")
    if abs(float(ctrl["brier"]) - brier95) > 1e-9:
        return fail("receipt always95 brier != reviewer")
    if abs(float(ctrl["delta_brier_always95_minus_council"]) - delta) > 1e-9:
        return fail("receipt ΔBrier != reviewer")
    if abs(float(boot["lo"]) - lo) > 1e-9 or abs(float(boot["hi"]) - hi) > 1e-9:
        return fail(f"receipt bootstrap CI [{boot.get('lo')},{boot.get('hi')}] != [{lo},{hi}]")
    if int(rec_bin80["n_correct"]) != k80 or int(rec_bin80["n"]) != n80:
        return fail("receipt 0.80 bin counts != reviewer")
    if abs(float(rec_bin80["wilson_lo"]) - wlo) > 1e-9:
        return fail("receipt Wilson lo != reviewer")
    if abs(float(rec_bin80["wilson_hi"]) - whi) > 1e-9:
        return fail("receipt Wilson hi != reviewer")
    if not (brier95 > brier and log95 < log_s and delta > 0):
        return fail("reviewer did not reproduce control separation")
    if not (lo > 0):
        return fail(f"bootstrap CI lower bound not >0: {lo}")
    rec_bins = (doc.get("reliability_diagram") or {}).get("discrete_stated_p_bins") or []
    if len(rec_bins) != len(bins):
        return fail("bin count mismatch")
    for rec, (p, n, k, obs) in zip(rec_bins, bins):
        if int(rec["n"]) != n or int(rec["n_correct"]) != k:
            return fail(f"bin {p} counts mismatch")
        if abs(float(rec["observed_accuracy"]) - obs) > 1e-9:
            return fail(f"bin {p} observed mismatch")

    tests = {t.get("id"): t.get("result") for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if tests.get("TST-0287-ALWAYS95-CONTROL") != "PASS":
        return fail("receipt test ALWAYS95-CONTROL is not PASS")
    if tests.get("TST-0287-RESOLUTION-HONESTY") != "PASS":
        return fail("receipt test RESOLUTION-HONESTY is not PASS")
    if str((doc.get("reviewer") or {}).get("verdict") or "").upper() != "PASS":
        return fail("receipt reviewer.verdict is not PASS")

    print("SUCCESS:TST-0287-probe2 independent statistics recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
