#!/usr/bin/env python3
"""Probe 2: planted both-states control + independent reviewer checks.

Reproduces:
  * shared-session (bad): randomised runner surfaces the planted pairs
  * isolated-session (good): no order-dependent pairs (state cannot leak)
  * same-order repeats: plant outcomes are stable (not C11 flake)
  * planted coin-flip under the SAME order: classified as flake, not a pair
  * C18 seed swap: seed-declared test moves; planted order pairs do not

The reviewer did not author the harness: this probe only consumes engine
entry points and re-derives the pairs from raw per-permutation outcomes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    PERM_SEEDS,
    PLANT_COIN,
    PLANT_POLLUTER,
    PLANT_READER,
    PLANT_VICTIM,
    PLANT_WRITER,
    SAME_ORDER_REPEATS,
    RunConfig,
    confirm_relative_order_pairs,
    run_campaign,
    same_order_repeat_campaign,
    seed_sensitivity_campaign,
    CORE_TESTS,
)

UNIT = "TST-0344"
REVIEWER_ID = "TST-0344-probe2-both-states-and-not-c11-c18"


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def correlational_candidates(report: dict) -> set[tuple[str, str]]:
    """Weak: relative-order split inside a 12-row matrix can be a decoy.

    A pass across three permutations is weak; a correlational split on a
    short shuffle sample is the same class of under-sampling. Candidates
    must be confirmed by executing the ordered pair both ways.
    """
    perms = report["permutations"]
    names = report["declaration_order"]
    found: set[tuple[str, str]] = set()
    for t in names:
        bits = {p["outcomes"].get(t) for p in perms}
        if len(bits) < 2:
            continue
        for s in names:
            if s == t:
                continue
            after_s: set[str] = set()
            t_first: set[str] = set()
            for p in perms:
                order = p["order"]
                if s not in order or t not in order:
                    continue
                outcome = p["outcomes"].get(t)
                if order.index(s) < order.index(t):
                    after_s.add(outcome)
                else:
                    t_first.add(outcome)
            if after_s and t_first and after_s != t_first:
                found.add((s, t))
    return found


def reviewer_pairs(report: dict) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Re-derive pairs: matrix candidates, then live [S,T] vs [T,S] confirmation."""
    candidates = correlational_candidates(report)
    confirmed_rows = confirm_relative_order_pairs(
        report["declaration_order"],
        report["varying_tests"],
        isolate_per_test=False,
        test_rng_seed=0,
        tests=CORE_TESTS,
    )
    confirmed = {tuple(r["pair"]) for r in confirmed_rows}
    return candidates, confirmed


def main() -> int:
    bad = run_campaign(RunConfig(seeds=PERM_SEEDS, plants=True, isolate_per_test=False))
    good = run_campaign(RunConfig(seeds=PERM_SEEDS, plants=True, isolate_per_test=True))
    no_plants = run_campaign(RunConfig(seeds=PERM_SEEDS, plants=False, isolate_per_test=False))

    stable = same_order_repeat_campaign(
        PERM_SEEDS[0], SAME_ORDER_REPEATS, include_coin_flip=False
    )
    flake = same_order_repeat_campaign(
        PERM_SEEDS[0], SAME_ORDER_REPEATS, include_coin_flip=True
    )
    c18 = seed_sensitivity_campaign(PERM_SEEDS[1])

    candidates, reconstructed = reviewer_pairs(bad)
    expected = {(PLANT_WRITER, PLANT_READER), (PLANT_POLLUTER, PLANT_VICTIM)}
    decoys = candidates - reconstructed

    payload = {
        "probe": "probe2-planted-control-both-states",
        "unit_id": UNIT,
        "reviewer_id": REVIEWER_ID,
        "independent": True,
        "bad_state": {
            "isolate_per_test": False,
            "minimal_pairs": bad["minimal_pairs"],
            "varying_tests": bad["varying_tests"],
            "failing_permutation_count": len(bad["failing_permutations"]),
        },
        "good_state_isolated": {
            "isolate_per_test": True,
            "minimal_pairs": good["minimal_pairs"],
            "varying_tests": good["varying_tests"],
            "constant_fail": good["constant_fail"],
        },
        "good_state_no_plants": {
            "plants": False,
            "minimal_pairs": no_plants["minimal_pairs"],
            "varying_tests": no_plants["varying_tests"],
            "failing_permutation_count": len(no_plants["failing_permutations"]),
        },
        "same_order_stable_plants": {
            "repeats": stable["repeats"],
            "unstable": stable["unstable_under_same_order"],
            "classification": stable["classification"],
        },
        "same_order_flake_plant": {
            "repeats": flake["repeats"],
            "unstable": flake["unstable_under_same_order"],
            "classification": flake["classification"],
        },
        "c18_seed_swap": {
            "changed_tests": c18["changed_tests"],
            "seed_test_changed": c18["seed_test_changed"],
            "plant_order_tests_changed": c18["plant_order_tests_changed"],
            "distinct_from_order_dependence": c18["distinct_from_order_dependence"],
        },
        "reviewer_matrix_candidates": sorted([list(p) for p in candidates]),
        "reviewer_confirmed_pairs": sorted([list(p) for p in reconstructed]),
        "reviewer_dropped_decoys": sorted([list(p) for p in decoys]),
        "reviewer_reconstructed_pairs": sorted([list(p) for p in reconstructed]),
        "both_states": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))

    if not bad["planted_pairs_all_found"]:
        return fail("bad-state did not surface planted pairs", bad["expected_planted_pairs"])
    if expected - reconstructed:
        return fail(
            "reviewer reconstruction missed planted pairs",
            {"expected": sorted(expected), "got": sorted(reconstructed)},
        )
    if reconstructed - expected:
        return fail("reviewer reconstruction extra pairs", sorted(reconstructed))
    if not decoys:
        return fail(
            "matrix produced no decoy candidates; confirmation would be vacuous on this seed set"
        )

    if good["varying_tests"]:
        return fail(
            "isolated session still shows order-varying tests",
            good["varying_tests"],
        )
    if good["minimal_pairs"]:
        return fail("isolated session still reports pairs", good["minimal_pairs"])
    if PLANT_READER not in good["constant_fail"]:
        return fail("isolated reader should always fail (token cannot leak)")

    if no_plants["varying_tests"] or no_plants["minimal_pairs"] or no_plants["failing_permutations"]:
        return fail("suite with plants removed is not order-invariant", no_plants["varying_tests"])

    if stable["unstable_under_same_order"]:
        return fail(
            "planted order-dep tests were unstable under the same order (would be C11)",
            stable["unstable_under_same_order"],
        )
    if PLANT_COIN not in flake["unstable_under_same_order"]:
        return fail("coin-flip plant was not unstable under the same order", flake)
    plant_ids = {PLANT_READER, PLANT_VICTIM, PLANT_WRITER, PLANT_POLLUTER}
    leaked = plant_ids.intersection(flake["unstable_under_same_order"])
    if leaked:
        return fail("order plants misclassified as flake under coin-flip campaign", sorted(leaked))

    if not c18["distinct_from_order_dependence"]:
        return fail("C18 seed swap did not isolate seed-sensitivity from order pairs", c18)

    print(
        f"bad_pairs={bad['minimal_pairs']} isolated_pairs={good['minimal_pairs']} "
        f"no_plant_pairs={no_plants['minimal_pairs']} "
        f"same_order_stable={stable['stable']} flake={flake['unstable_under_same_order']} "
        f"c18={c18['changed_tests']}"
    )
    print(
        f"SUCCESS:{UNIT}-probe2 both-states control, "
        f"reviewer reconstructed {sorted(reconstructed)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
