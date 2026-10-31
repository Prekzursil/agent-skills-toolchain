"""TST-0288 deterministic gold-set aggregation harness (seed 288).

Seven voters M0-M6 emit probabilities on 280 binary cases (80 calibration,
200 held-out test). Calibration weights = inverse calibration-case Brier;
role weights fixed; random weights drawn under the same seed. Every method
ranks by mean Brier over the IDENTICAL test cases (paired). The three
receipt controls live here: weight-source ablation, random-weight null,
always-95 separation. The production council corpus is absent on this host
(as the receipt records), so the deterministic gold set stands in and is
labeled as such in every output.
"""
from __future__ import annotations

import random
from typing import Any

SEED = 288
N_CAL = 80
N_TEST = 200
N_BOOT = 2000
N_PERM = 4000
VOTERS = ["M0", "M1", "M2", "M3", "M4", "M5", "M6"]
ROLE_WEIGHTS = {
    "M0": 0.16,
    "M1": 0.16,
    "M2": 0.08,
    "M3": 0.24,
    "M4": 0.08,
    "M5": 0.20,
    "M6": 0.08,
}
METHODS = [
    "majority",
    "supermajority",
    "unanimity",
    "quorum",
    "veto",
    "abstention",
    "judge",
    "score",
    "approval",
    "condorcet",
    "ranked_choice",
    "consent",
    "juror",
    "delegation",
    "weighted_calibration",
    "weighted_role",
    "random_weighted",
    "bayes_log",
    "bayes_log_calibration",
    "always_95",
]


def gold_set(seed: int = SEED):
    rng = random.Random(seed)
    truths = [rng.random() < 0.5 for _ in range(N_CAL + N_TEST)]
    accs = {v: 0.62 + 0.12 * rng.random() for v in VOTERS}

    def draw(t: bool, v: str) -> float:
        p_correct = accs[v]
        agree = rng.random() < p_correct
        if agree:
            p = 0.75 + 0.20 * rng.random()
        else:
            p = 0.05 + 0.15 * rng.random()
        return p

    votes = [{v: draw(t, v) for v in VOTERS} for t in truths]
    return truths, votes, accs


def brier(p: float, t: bool) -> float:
    return (p - (1.0 if t else 0.0)) ** 2


def calibrate(truths: list[bool], votes: list[dict[str, float]]):
    mb = {}
    for v in VOTERS:
        mb[v] = sum(brier(votes[i][v], truths[i]) for i in range(N_CAL)) / N_CAL
    raw = {v: 1.0 / (mb[v] + 0.01) for v in VOTERS}
    z = sum(raw.values())
    return {v: w / z for v, w in raw.items()}, mb


def _weighted(vi: dict[str, float], w: dict[str, float]) -> float:
    return sum(w[v] * vi[v] for v in VOTERS)


def aggregate(method: str, vi: dict[str, float], weights: dict) -> float:
    ps = [vi[v] for v in VOTERS]
    if method == "majority":
        return sum(ps) / len(ps)
    if method == "supermajority":
        return sum(1 for p in ps if p >= 0.6) / len(ps)
    if method == "unanimity":
        return 1.0 if all(p >= 0.5 for p in ps) else 0.0
    if method == "quorum":
        n_yes = sum(1 for p in ps if p >= 0.5)
        return 1.0 if n_yes >= 4 else (0.5 if n_yes >= 3 else 0.0)
    if method == "veto":
        return 1.0 if all(p >= 0.5 for p in ps) else (sum(ps) / len(ps)) * 0.5
    if method == "abstention":
        live = [p for p in ps if abs(p - 0.5) > 0.08]
        return (sum(live) / len(live)) if live else 0.5
    if method == "judge":
        sp = sorted(ps)
        return sp[len(sp) // 2]
    if method == "score":
        return max(0.0, min(1.0, sum(ps) / len(ps)))
    if method == "approval":
        return sum(1 for p in ps if p > 0.5) / len(ps)
    if method == "condorcet":
        return 1.0 if sum(1 for p in ps if p >= 0.5) > len(ps) / 2 else 0.0
    if method == "ranked_choice":
        ordered = sorted(ps, reverse=True)
        return sum(ordered[:4]) / 4
    if method == "consent":
        return sum(1 for p in ps if p > 0.3) / len(ps)
    if method == "juror":
        strong = [p for p in ps if p >= 0.75 or p <= 0.25]
        return (sum(strong) / len(strong)) if strong else sum(ps) / len(ps)
    if method == "delegation":
        return max(ps)
    if method == "weighted_calibration":
        return _weighted(vi, weights["calibration"])
    if method == "weighted_role":
        return _weighted(vi, weights["role"])
    if method == "random_weighted":
        return _weighted(vi, weights["random"])
    if method in ("bayes_log", "bayes_log_calibration"):
        eps = 1e-3
        w = (
            weights["calibration"]
            if method.endswith("calibration")
            else {v: 1.0 for v in VOTERS}
        )
        odds = 1.0
        for v in VOTERS:
            p = min(1 - eps, max(eps, vi[v]))
            odds *= (p / (1 - p)) ** w[v]
        return odds / (1 + odds)
    if method == "bayes_linear":
        return _weighted(vi, {v: 1.0 for v in VOTERS})
    if method == "always_95":
        return 0.95
    raise KeyError(method)


def _paired(d1: list[float], d2: list[float]) -> dict[str, Any]:
    diffs = [a - b for a, b in zip(d1, d2)]
    md = sum(diffs) / len(diffs)
    rng = random.Random(SEED + 2)
    ge = 0
    for _ in range(N_PERM):
        flipped = [d if rng.random() < 0.5 else -d for d in diffs]
        if sum(flipped) / len(flipped) >= md - 1e-12:
            ge += 1
    p_one = (ge + 1) / (N_PERM + 1)
    p = min(1.0, 2 * p_one)
    return {"mean_diff": md, "p_two_sided": p, "n_perm": N_PERM, "n": N_TEST}


def run() -> dict[str, Any]:
    truths, votes, accs = gold_set()
    cal_w, member_brier = calibrate(truths, votes)
    rng = random.Random(SEED + 1)
    rnd = [rng.random() for _ in VOTERS]
    z = sum(rnd)
    random_w = {v: r / z for v, r in zip(VOTERS, rnd)}
    weights = {"calibration": cal_w, "role": ROLE_WEIGHTS, "random": random_w}
    test_idx = list(range(N_CAL, N_CAL + N_TEST))
    per_case: dict[str, list[float]] = {}
    mean_brier: dict[str, float] = {}
    for m in METHODS:
        per = [brier(aggregate(m, votes[i], weights), truths[i]) for i in test_idx]
        per_case[m] = per
        mean_brier[m] = sum(per) / len(per)
    ranking = sorted(METHODS, key=lambda m: mean_brier[m])
    return {
        "seed": SEED,
        "n_cal": N_CAL,
        "n_test": N_TEST,
        "production_corpus": "ABSENT",
        "simulator": "command-center/p2-wave/probes/TST-0288/harness.py",
        "weights": weights,
        "member_brier_cal": member_brier,
        "ranking_by_mean_brier": [m for m in ranking if m != "always_95"],
        "mean_brier": mean_brier,
        "best_method": ranking[0],
        "weighting_beats_majority": (
            mean_brier["weighted_calibration"] < mean_brier["majority"]
            or mean_brier["weighted_role"] < mean_brier["majority"]
        ),
        "random_weights_beats_majority": (
            mean_brier["random_weighted"] < mean_brier["majority"]
        ),
        "ablation": {
            "calibration_mean_brier": mean_brier["weighted_calibration"],
            "role_mean_brier": mean_brier["weighted_role"],
            "calibration_vs_majority": _paired(
                per_case["weighted_calibration"], per_case["majority"]
            ),
            "role_vs_majority": _paired(
                per_case["weighted_role"], per_case["majority"]
            ),
        },
        "best_vs_majority": _paired(
            per_case[ranking[0]], per_case["majority"]
        ),
        "metric_separates_always_95": (
            mean_brier["always_95"] > mean_brier["majority"]
        ),
        "per_case": per_case,
        "voter_accs": accs,
    }
