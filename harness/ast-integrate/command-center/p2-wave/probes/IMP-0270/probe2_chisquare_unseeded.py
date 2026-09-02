#!/usr/bin/env python3
"""Named probe 2: chi-square stratum fit + unseeded negative control.

Required tests:
  statistical: stratum proportion check over 1000 draws
  negative control: unseeded RNG must break the reproducibility test

Independent of the author's summary: this probe re-implements the documented
algorithm with its own ``random.Random`` calls and recomputes chi-square from
the raw per-draw census. A uniform sampler must FAIL the requested-quota
chi-square (both-states discriminator).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.participants.select_random import (  # noqa: E402
    SamplingError,
    accumulate_stratum_counts,
    chi_square_gof,
    roster_matches,
    select_stratified,
    select_uniform,
    stratum_expected_from_quotas,
)
from pool import (  # noqa: E402
    N_DRAWS,
    REQUESTED_STRATA,
    SEED_A,
    UNIFORM_K,
    build_pool,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0270-probe2 {msg}")
    return 1


def independent_uniform_ids(pool: list[dict], k: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    ordered = sorted(pool, key=lambda p: p["id"])
    return [p["id"] for p in rng.sample(ordered, k)]


def independent_stratified_ids(
    pool: list[dict], quotas: dict[str, int], seed: int
) -> list[str]:
    rng = random.Random(seed)
    by_stratum: dict[str, list[dict]] = {}
    for participant in sorted(pool, key=lambda p: p["id"]):
        by_stratum.setdefault(participant["vendor"], []).append(participant)
    chosen: list[dict] = []
    for key in sorted(quotas):
        chosen.extend(rng.sample(by_stratum[key], quotas[key]))
    rng.shuffle(chosen)
    return [p["id"] for p in chosen]


def independent_chi2(observed: dict[str, float], expected: dict[str, float]) -> float:
    chi2 = 0.0
    for key, exp in expected.items():
        obs = observed.get(key, 0.0)
        chi2 += (obs - exp) ** 2 / exp
    return chi2


def reproducibility_holds(left: dict, right: dict) -> bool:
    return roster_matches(left, right)


def main() -> int:
    pool = build_pool()

    module_u = select_uniform(pool, UNIFORM_K, seed=SEED_A)
    indep_u = independent_uniform_ids(pool, UNIFORM_K, SEED_A)
    if module_u["roster_ids"] != indep_u:
        return fail(
            f"independent uniform replay diverged module={module_u['roster_ids']} "
            f"independent={indep_u}"
        )
    module_s = select_stratified(pool, REQUESTED_STRATA, seed=SEED_A)
    indep_s = independent_stratified_ids(pool, REQUESTED_STRATA, SEED_A)
    if module_s["roster_ids"] != indep_s:
        return fail(
            f"independent stratified replay diverged module={module_s['roster_ids']} "
            f"independent={indep_s}"
        )

    stratified_runs = [
        select_stratified(pool, REQUESTED_STRATA, seed=SEED_A + i)
        for i in range(N_DRAWS)
    ]
    observed_s = accumulate_stratum_counts(stratified_runs)
    expected_s = stratum_expected_from_quotas(REQUESTED_STRATA, N_DRAWS)
    fit_s = chi_square_gof(observed_s, expected_s)
    hand_chi2 = independent_chi2(observed_s, expected_s)
    if abs(hand_chi2 - fit_s["chi_square"]) > 1e-12:
        return fail(
            f"chi-square implementations disagree module={fit_s['chi_square']} "
            f"hand={hand_chi2}"
        )
    if not fit_s["proportions_match"]:
        return fail(
            f"stratified chi-square rejected requested quotas chi2={fit_s['chi_square']} "
            f"obs={observed_s} exp={expected_s}"
        )
    if fit_s["chi_square"] != 0.0:
        return fail(
            f"exact-quota stratified sampler produced chi2={fit_s['chi_square']} "
            f"(expected 0 when every draw fills quotas exactly)"
        )

    uniform_runs = [
        select_uniform(pool, UNIFORM_K, seed=SEED_A + 10_000 + i)
        for i in range(N_DRAWS)
    ]
    observed_u = accumulate_stratum_counts(uniform_runs)
    fit_u = chi_square_gof(observed_u, expected_s)
    if fit_u["proportions_match"]:
        return fail(
            "uniform sampler matched requested-quota chi-square; discriminator inert "
            f"chi2={fit_u['chi_square']} obs={observed_u}"
        )

    # Negative control: unseeded pair must fail the reproducibility test.
    # Seeded pair must pass (both-states). Retry unseeded on the tiny-probability
    # collision rather than treating a fluke match as a frozen RNG.
    seeded_ok = reproducibility_holds(
        select_uniform(pool, UNIFORM_K, seed=SEED_A),
        select_uniform(pool, UNIFORM_K, seed=SEED_A),
    )
    if not seeded_ok:
        return fail("seeded reproducibility test failed on the good state")

    unseeded_fired = False
    unseeded_pair = None
    for _ in range(16):
        a = select_uniform(pool, UNIFORM_K, seed=None)
        b = select_uniform(pool, UNIFORM_K, seed=None)
        if not reproducibility_holds(a, b):
            unseeded_fired = True
            unseeded_pair = (a["roster_ids"], b["roster_ids"], a["seed"], b["seed"])
            break
    if not unseeded_fired:
        return fail("unseeded RNG did not break the reproducibility test")

    # Loud under-fill: a quota larger than the stratum must not silently shrink.
    try:
        select_stratified(pool, {"anthropic": 99, "openai": 1, "google": 1}, seed=SEED_A)
        return fail("oversize quota did not raise SamplingError")
    except SamplingError as exc:
        underfill_message = str(exc)
        if "refusing to under-fill" not in underfill_message:
            return fail(f"oversize quota error was not loud under-fill: {exc}")

    summary = {
        "independent_replay_match": True,
        "n_draws": N_DRAWS,
        "pass": True,
        "probe": "probe2-chisquare-unseeded",
        "seeded_reproducibility_silent_on_good": True,
        "stratified_chi_square": fit_s["chi_square"],
        "stratified_expected": expected_s,
        "stratified_observed": observed_s,
        "stratified_proportions_match": True,
        "underfill_refused": True,
        "uniform_chi_square_vs_requested": fit_u["chi_square"],
        "uniform_observed": observed_u,
        "uniform_requested_chi_square_rejects": True,
        "unit_id": "IMP-0270",
        "unseeded_reproducibility_fired": True,
        "unseeded_roster_a": unseeded_pair[0] if unseeded_pair else None,
        "unseeded_roster_b": unseeded_pair[1] if unseeded_pair else None,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"chi2_stratified={fit_s['chi_square']} chi2_uniform_vs_requested="
        f"{fit_u['chi_square']:.4f} unseeded_fired={unseeded_fired} "
        f"independent_replay=True n_draws={N_DRAWS}"
    )
    print("SUCCESS:IMP-0270-probe2 chi-square and unseeded negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
