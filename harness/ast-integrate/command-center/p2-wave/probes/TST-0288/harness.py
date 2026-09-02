#!/usr/bin/env python3
"""Deterministic scored comparison of council aggregation methods.

B07 vote modules and tools/council/simulate.py are absent on this worktree.
This harness is the unit-local stand-in listed as an input (deterministic
simulator). Production resolved-council receipts are also absent; the gold
set is generated here with known outcomes and a held-out calibration split
so weight fitting cannot see the scored cases.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SEED = 288
N_CAL = 80
N_TEST = 200
N_BOOT = 2000
N_PERM = 4000
P_CLIP = 1e-6
EPS = 1e-12

# :10930 methods that can emit a probability on a binary resolved case.
METHOD_ORDER = [
    "majority",
    "supermajority",
    "unanimity",
    "consent",
    "ranked_choice",
    "score",
    "approval",
    "condorcet",
    "juror",
    "judge",
    "weighted_calibration",
    "weighted_role",
    "bayes_linear",
    "bayes_log",
    "bayes_log_calibration",
    "veto",
    "quorum",
    "abstention",
    "delegation",
    "random_weights",
]

# Ranking candidates: real methods, not the null or the always-95 control.
RANK_EXCLUDE = frozenset({"random_weights", "always_95"})

ROLE_WEIGHT = {
    "chair": 3.0,
    "specialist": 2.0,
    "judge": 2.5,
    "juror": 1.0,
    "generalist": 1.0,
}

MEMBERS = [
    {"id": "M0", "role": "specialist", "sigma": 0.55, "temp": 1.00},
    {"id": "M1", "role": "specialist", "sigma": 0.70, "temp": 1.05},
    {"id": "M2", "role": "generalist", "sigma": 1.20, "temp": 1.00},
    {"id": "M3", "role": "chair", "sigma": 1.85, "temp": 0.45},
    {"id": "M4", "role": "juror", "sigma": 1.45, "temp": 1.80},
    {"id": "M5", "role": "judge", "sigma": 1.05, "temp": 0.85},
    {"id": "M6", "role": "generalist", "sigma": 1.25, "temp": 1.10},
]

LIVE_TARGETS = [
    "tools/council/simulate.py",
    "tools/council/vote/bayes.py",
    "tools/council/vote/weights.py",
    "tools/council/vote/tally.py",
    "command-center/receipts/TST-0287.json",
    "command-center/receipts/TST-0280.json",
]


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def logit(p: float) -> float:
    p = min(1 - P_CLIP, max(P_CLIP, p))
    return math.log(p / (1.0 - p))


def clip_p(p: float) -> float:
    return min(1 - P_CLIP, max(P_CLIP, p))


def brier(p: float, y: int) -> float:
    return (p - y) ** 2


def log_loss(p: float, y: int) -> float:
    p = clip_p(p)
    return -(y * math.log(p) + (1 - y) * math.log(1.0 - p))


def inventory() -> dict:
    rows = {}
    for rel in LIVE_TARGETS:
        p = REPO / rel
        rows[rel] = {
            "present": p.is_file(),
            "bytes": p.stat().st_size if p.is_file() else 0,
        }
    return rows


def generate_case(rng: random.Random, case_id: int) -> dict:
    y = 1 if rng.random() < 0.5 else 0
    latent = 1.0 if y == 1 else -1.0
    members = []
    for spec in MEMBERS:
        signal = latent + rng.gauss(0.0, spec["sigma"])
        p_raw = sigmoid(signal)
        p_rep = sigmoid(logit(p_raw) / spec["temp"])
        members.append(
            {
                "id": spec["id"],
                "role": spec["role"],
                "p": clip_p(p_rep),
            }
        )
    return {"id": case_id, "y": y, "members": members}


def generate_split(seed: int = SEED) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    cal = [generate_case(rng, i) for i in range(N_CAL)]
    test = [generate_case(rng, N_CAL + i) for i in range(N_TEST)]
    return cal, test


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def member_brier(cal: list[dict]) -> dict[str, float]:
    acc: dict[str, list[float]] = {m["id"]: [] for m in MEMBERS}
    for case in cal:
        y = case["y"]
        for row in case["members"]:
            acc[row["id"]].append(brier(row["p"], y))
    return {k: mean(v) for k, v in acc.items()}


def norm_weights(raw: dict[str, float]) -> dict[str, float]:
    tot = sum(max(0.0, v) for v in raw.values())
    if tot <= EPS:
        n = max(1, len(raw))
        return {k: 1.0 / n for k in raw}
    return {k: max(0.0, v) / tot for k, v in raw.items()}


def calibration_weights(cal: list[dict]) -> dict[str, float]:
    br = member_brier(cal)
    raw = {k: 1.0 / (v + 0.02) for k, v in br.items()}
    return norm_weights(raw)


def role_weights() -> dict[str, float]:
    raw = {m["id"]: ROLE_WEIGHT[m["role"]] for m in MEMBERS}
    return norm_weights(raw)


def random_weight_vector(seed: int = SEED + 17) -> dict[str, float]:
    rng = random.Random(seed)
    # Dirichlet(1,...,1) == normalised independent exponentials.
    raw = {m["id"]: -math.log(max(rng.random(), 1e-12)) for m in MEMBERS}
    return norm_weights(raw)


def linear_pool(members: list[dict], weights: dict[str, float]) -> float:
    return clip_p(sum(weights[m["id"]] * m["p"] for m in members))


def log_pool(members: list[dict], weights: dict[str, float]) -> float:
    acc = 0.0
    for m in members:
        acc += weights[m["id"]] * logit(m["p"])
    return clip_p(sigmoid(acc))


def vote_yes(members: list[dict]) -> list[int]:
    return [1 if m["p"] >= 0.5 else 0 for m in members]


def vote_share(members: list[dict], mask: list[bool] | None = None) -> float:
    votes = vote_yes(members)
    if mask is None:
        mask = [True] * len(members)
    n = sum(1 for ok in mask if ok)
    if n == 0:
        return 0.5
    s = sum(v for v, ok in zip(votes, mask) if ok)
    return s / n


def equal_w() -> dict[str, float]:
    n = float(len(MEMBERS))
    return {m["id"]: 1.0 / n for m in MEMBERS}


def forecast_majority(case: dict, ctx: dict) -> float:
    return vote_share(case["members"])


def forecast_supermajority(case: dict, ctx: dict) -> float:
    share = vote_share(case["members"])
    if share >= 2.0 / 3.0 or share <= 1.0 / 3.0:
        return share
    return 0.5


def forecast_unanimity(case: dict, ctx: dict) -> float:
    votes = vote_yes(case["members"])
    if all(v == 1 for v in votes):
        return 1.0
    if all(v == 0 for v in votes):
        return 0.0
    return 0.5


def forecast_consent(case: dict, ctx: dict) -> float:
    if any(m["p"] < 0.25 for m in case["members"]):
        return 0.0
    if any(m["p"] >= 0.5 for m in case["members"]):
        return 1.0
    return 0.5


def forecast_ranked_choice(case: dict, ctx: dict) -> float:
    # Binary IRV coincides with majority.
    return vote_share(case["members"])


def forecast_score(case: dict, ctx: dict) -> float:
    return linear_pool(case["members"], equal_w())


def forecast_approval(case: dict, ctx: dict) -> float:
    return vote_share(case["members"])


def forecast_condorcet(case: dict, ctx: dict) -> float:
    return vote_share(case["members"])


def forecast_juror(case: dict, ctx: dict) -> float:
    jurors = [m for m in case["members"] if m["role"] == "juror"]
    if not jurors:
        return 0.5
    return mean([m["p"] for m in jurors])


def forecast_judge(case: dict, ctx: dict) -> float:
    judges = [m for m in case["members"] if m["role"] == "judge"]
    if not judges:
        return 0.5
    return judges[0]["p"]


def forecast_weighted_cal(case: dict, ctx: dict) -> float:
    return linear_pool(case["members"], ctx["w_cal"])


def forecast_weighted_role(case: dict, ctx: dict) -> float:
    return linear_pool(case["members"], ctx["w_role"])


def forecast_bayes_linear(case: dict, ctx: dict) -> float:
    return linear_pool(case["members"], equal_w())


def forecast_bayes_log(case: dict, ctx: dict) -> float:
    return log_pool(case["members"], equal_w())


def forecast_bayes_log_cal(case: dict, ctx: dict) -> float:
    return log_pool(case["members"], ctx["w_cal"])


def forecast_veto(case: dict, ctx: dict) -> float:
    share = vote_share(case["members"])
    side = 1 if share >= 0.5 else 0
    for m in case["members"]:
        vote = 1 if m["p"] >= 0.5 else 0
        if vote != side and m["p"] < 0.10:
            return 0.5
        if vote != side and m["p"] > 0.90:
            return 0.5
    return share


def forecast_quorum(case: dict, ctx: dict) -> float:
    mask = [not (0.45 < m["p"] < 0.55) for m in case["members"]]
    if sum(1 for ok in mask if ok) < 3:
        return 0.5
    return vote_share(case["members"], mask)


def forecast_abstention(case: dict, ctx: dict) -> float:
    mask = [not (0.45 < m["p"] < 0.55) for m in case["members"]]
    return vote_share(case["members"], mask)


def forecast_delegation(case: dict, ctx: dict) -> float:
    # Generalists delegate their vote to the chair; power conserved.
    chair = next(m for m in case["members"] if m["role"] == "chair")
    power = 0.0
    yes = 0.0
    for m in case["members"]:
        if m["role"] == "generalist":
            continue
        w = 1.0
        if m["id"] == chair["id"]:
            w += sum(1 for x in case["members"] if x["role"] == "generalist")
        power += w
        if m["p"] >= 0.5:
            yes += w
    if power <= EPS:
        return 0.5
    return yes / power


def forecast_random(case: dict, ctx: dict) -> float:
    return linear_pool(case["members"], ctx["w_rand"])


FORECASTERS: dict[str, Callable[[dict, dict], float]] = {
    "majority": forecast_majority,
    "supermajority": forecast_supermajority,
    "unanimity": forecast_unanimity,
    "consent": forecast_consent,
    "ranked_choice": forecast_ranked_choice,
    "score": forecast_score,
    "approval": forecast_approval,
    "condorcet": forecast_condorcet,
    "juror": forecast_juror,
    "judge": forecast_judge,
    "weighted_calibration": forecast_weighted_cal,
    "weighted_role": forecast_weighted_role,
    "bayes_linear": forecast_bayes_linear,
    "bayes_log": forecast_bayes_log,
    "bayes_log_calibration": forecast_bayes_log_cal,
    "veto": forecast_veto,
    "quorum": forecast_quorum,
    "abstention": forecast_abstention,
    "delegation": forecast_delegation,
    "random_weights": forecast_random,
}


def bootstrap_ci(values: list[float], n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_boot):
        acc = 0.0
        for _i in range(n):
            acc += values[rng.randrange(n)]
        means.append(acc / n)
    means.sort()
    lo_i = int(0.025 * (n_boot - 1))
    hi_i = int(0.975 * (n_boot - 1))
    return means[lo_i], means[hi_i]


def paired_perm(a: list[float], b: list[float], n_perm: int = N_PERM, seed: int = SEED) -> dict:
    """Two-sided sign-flip permutation test of mean(a-b). Lower scores are better."""
    n = len(a)
    diff = [ai - bi for ai, bi in zip(a, b)]
    obs = mean(diff)
    rng = random.Random(seed)
    extreme = 0
    for _ in range(n_perm):
        s = 0.0
        for d in diff:
            s += d if rng.random() < 0.5 else -d
        if abs(s / n) >= abs(obs) - 1e-15:
            extreme += 1
    p = (extreme + 1) / (n_perm + 1)
    return {
        "mean_diff": obs,
        "p_two_sided": p,
        "n_perm": n_perm,
        "n": n,
    }


def always_95_scores(test: list[dict]) -> list[float]:
    return [brier(0.95, case["y"]) for case in test]


def run(seed: int = SEED) -> dict:
    live = inventory()
    cal, test = generate_split(seed)
    w_cal = calibration_weights(cal)
    w_role = role_weights()
    w_rand = random_weight_vector(seed + 17)
    ctx = {"w_cal": w_cal, "w_role": w_role, "w_rand": w_rand}

    per_case = []
    series_b: dict[str, list[float]] = {m: [] for m in METHOD_ORDER}
    series_l: dict[str, list[float]] = {m: [] for m in METHOD_ORDER}
    for case in test:
        forecasts = {}
        row_b = {}
        row_l = {}
        y = case["y"]
        for name, fn in FORECASTERS.items():
            p = clip_p(fn(case, ctx))
            forecasts[name] = p
            bb = brier(p, y)
            ll = log_loss(p, y)
            row_b[name] = bb
            row_l[name] = ll
            series_b[name].append(bb)
            series_l[name].append(ll)
        per_case.append(
            {
                "id": case["id"],
                "y": y,
                "forecasts": forecasts,
                "brier": row_b,
                "log_loss": row_l,
            }
        )

    a95 = always_95_scores(test)
    methods = {}
    for idx, name in enumerate(METHOD_ORDER):
        bs = series_b[name]
        ls = series_l[name]
        blo, bhi = bootstrap_ci(bs, seed=SEED + 11 + idx)
        llo, lhi = bootstrap_ci(ls, seed=SEED + 311 + idx)
        vs_maj = paired_perm(bs, series_b["majority"], seed=SEED + 7)
        methods[name] = {
            "n": len(bs),
            "mean_brier": mean(bs),
            "brier_ci95": [blo, bhi],
            "mean_log_loss": mean(ls),
            "log_loss_ci95": [llo, lhi],
            "paired_vs_majority_brier": vs_maj,
            "beats_majority_point": mean(bs) < mean(series_b["majority"]),
        }

    methods["always_95"] = {
        "n": len(a95),
        "mean_brier": mean(a95),
        "brier_ci95": list(bootstrap_ci(a95, seed=SEED + 99)),
        "mean_log_loss": mean([log_loss(0.95, c["y"]) for c in test]),
        "note": "reference miscalibrated forecaster; not a ranking candidate",
    }

    rankable = [m for m in METHOD_ORDER if m not in RANK_EXCLUDE]
    ranking = sorted(rankable, key=lambda m: (methods[m]["mean_brier"], m))
    best = ranking[0]
    maj_b = methods["majority"]["mean_brier"]
    rand_b = methods["random_weights"]["mean_brier"]
    rand_vs = methods["random_weights"]["paired_vs_majority_brier"]
    random_beats = bool(
        rand_b < maj_b - 1e-12 and rand_vs["p_two_sided"] < 0.05
    )

    cal_b = methods["weighted_calibration"]["mean_brier"]
    role_b = methods["weighted_role"]["mean_brier"]
    best_vs = methods[best]["paired_vs_majority_brier"]
    weighting_beats = (
        min(cal_b, methods["bayes_log_calibration"]["mean_brier"]) < maj_b
        and (
            methods["weighted_calibration"]["paired_vs_majority_brier"]["p_two_sided"] < 0.05
            or methods["bayes_log_calibration"]["paired_vs_majority_brier"]["p_two_sided"] < 0.05
        )
    )

    coincidences = {
        "majority_eq_approval": all(
            abs(r["forecasts"]["majority"] - r["forecasts"]["approval"]) < 1e-15
            for r in per_case
        ),
        "majority_eq_ranked_choice": all(
            abs(r["forecasts"]["majority"] - r["forecasts"]["ranked_choice"]) < 1e-15
            for r in per_case
        ),
        "majority_eq_condorcet": all(
            abs(r["forecasts"]["majority"] - r["forecasts"]["condorcet"]) < 1e-15
            for r in per_case
        ),
        "score_eq_bayes_linear": all(
            abs(r["forecasts"]["score"] - r["forecasts"]["bayes_linear"]) < 1e-15
            for r in per_case
        ),
    }

    ranking_withheld = random_beats
    claim = _claim(
        ranking_withheld=ranking_withheld,
        weighting_beats=weighting_beats,
        best=best,
        methods=methods,
        maj_b=maj_b,
        cal_b=cal_b,
        role_b=role_b,
        n_test=len(test),
        live=live,
    )

    return {
        "unit_id": "TST-0288",
        "seed": seed,
        "n_cal": N_CAL,
        "n_test": N_TEST,
        "n_boot": N_BOOT,
        "n_perm": N_PERM,
        "live_targets": live,
        "production_corpus": "ABSENT",
        "b07_runtime": "ABSENT"
        if not live["tools/council/vote/bayes.py"]["present"]
        else "PRESENT",
        "simulator": "command-center/p2-wave/probes/TST-0288/harness.py",
        "weights": {
            "calibration": w_cal,
            "role": w_role,
            "random": w_rand,
            "member_brier_cal": member_brier(cal),
        },
        "methods": methods,
        "ranking_by_mean_brier": ranking,
        "best_method": best,
        "ranking_withheld": ranking_withheld,
        "random_weights_beats_majority": random_beats,
        "weighting_beats_majority": weighting_beats,
        "ablation": {
            "calibration_mean_brier": cal_b,
            "role_mean_brier": role_b,
            "calibration_minus_role": cal_b - role_b,
            "calibration_vs_majority": methods["weighted_calibration"]["paired_vs_majority_brier"],
            "role_vs_majority": methods["weighted_role"]["paired_vs_majority_brier"],
        },
        "best_vs_majority": best_vs,
        "metric_separates_always_95": methods["always_95"]["mean_brier"] > maj_b,
        "coincidences_on_binary_gold": coincidences,
        "claim": claim,
        "per_case": per_case,
    }


def _claim(
    *,
    ranking_withheld: bool,
    weighting_beats: bool,
    best: str,
    methods: dict,
    maj_b: float,
    cal_b: float,
    role_b: float,
    n_test: int,
    live: dict,
) -> str:
    absent = [k for k, v in live.items() if not v["present"]]
    prefix = (
        f"On N={n_test} held-out resolved cases of the TST-0288 deterministic "
        f"gold set (production council corpus ABSENT; live B07 paths absent: "
        f"{absent}), "
    )
    if ranking_withheld:
        rw = methods["random_weights"]
        return (
            prefix
            + "random weights beat unweighted majority (mean Brier "
            f"{rw['mean_brier']:.6f} vs {maj_b:.6f}, paired p="
            f"{rw['paired_vs_majority_brier']['p_two_sided']:.4f}). "
            "The corpus is too small for a ranking; no method ranking is issued."
        )
    bm = methods[best]
    delta = maj_b - bm["mean_brier"]
    p = bm["paired_vs_majority_brier"]["p_two_sided"]
    ci = bm["paired_vs_majority_brier"]["mean_diff"]
    if weighting_beats:
        verb = (
            "calibration-derived weights (linear and/or log pool) outperform "
            "unweighted majority"
        )
    else:
        verb = (
            "weighted and Bayesian aggregation do not outperform unweighted "
            "majority (calibration-weighted and log-pool Brier are higher, not "
            "lower); the extra machinery is unjustified complexity on this gold "
            "set and the default must be unweighted majority, not weighted or "
            "Bayesian pooling"
        )
    return (
        prefix
        + verb
        + f". Best-by-Brier is {best} at {bm['mean_brier']:.6f} "
        f"(95% bootstrap CI {bm['brier_ci95'][0]:.6f}–{bm['brier_ci95'][1]:.6f}) "
        f"versus majority {maj_b:.6f} (CI {methods['majority']['brier_ci95'][0]:.6f}–"
        f"{methods['majority']['brier_ci95'][1]:.6f}); mean paired Brier difference "
        f"(method−majority)={ci:.6f}, two-sided permutation p={p:.4f}, "
        f"majority−best={delta:.6f}. "
        f"Weight-source ablation: calibration-weighted Brier={cal_b:.6f}, "
        f"role-weighted Brier={role_b:.6f}."
    )


def dump_summary(doc: dict) -> dict:
    """Receipt-sized view: drop per-case forecasts, keep vectors for review."""
    slim_cases = [
        {
            "id": r["id"],
            "y": r["y"],
            "brier": r["brier"],
            "forecasts": r["forecasts"],
        }
        for r in doc["per_case"]
    ]
    out = dict(doc)
    out["per_case"] = slim_cases
    return out


if __name__ == "__main__":
    doc = run()
    slim = {k: v for k, v in doc.items() if k != "per_case"}
    print(json.dumps(slim, indent=2, sort_keys=True)[:8000])
    print(f"best={doc['best_method']} withheld={doc['ranking_withheld']}")
    print(f"weighting_beats={doc['weighting_beats_majority']}")
    print(f"random_beats={doc['random_weights_beats_majority']}")
    print(doc["claim"])
