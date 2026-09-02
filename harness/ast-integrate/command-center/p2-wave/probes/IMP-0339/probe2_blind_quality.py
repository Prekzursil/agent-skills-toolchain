#!/usr/bin/env python3
"""Named probe 2: promoted set vs random subset on a blind quality rating.

Control required by IMP-0339: if the maturity bar is decorative, a random
subset of the same size is indistinguishable from the promoted set.
A title-length decorative bar is the known-broken control that must NOT
match the real bar's margin.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE / "fixtures"))

from planted import EXPECTED_PROMOTED, build_ideas  # noqa: E402
from tools.council.artifacts.option_cards import promote  # noqa: E402
from tools.council.artifacts.quality_rater import (  # noqa: E402
    independent_quality,
    mean_quality,
    strip_for_blind,
    title_length_select,
)

RANDOM_SEED = 20260824
PERMUTATION_SEED = 339
PERMUTATIONS = 400
MARGIN = 15.0


def _by_id(ideas: list[dict], ids: list[str]) -> list[dict]:
    index = {i["idea_id"]: i for i in ideas}
    return [index[i] for i in ids]


def main() -> int:
    ideas = build_ideas()
    result = promote(ideas, evidence_root=REPO)
    promoted_ids = [c["source_idea_id"] for c in result.cards]
    if promoted_ids != EXPECTED_PROMOTED:
        print("FAILED:IMP-0339-probe2 promotion set drifted from planted key")
        return 1
    k = result.n_promoted
    if k != 8:
        print(f"FAILED:IMP-0339-probe2 k={k} want=8")
        return 1

    promoted_ideas = _by_id(ideas, promoted_ids)
    for idea in promoted_ideas:
        stripped = strip_for_blind(idea)
        independent_quality(stripped)

    rng = random.Random(RANDOM_SEED)
    random_subset = rng.sample(list(ideas), k)
    decorative = title_length_select(ideas, k)

    promoted_mean = mean_quality(promoted_ideas)
    random_mean = mean_quality(random_subset)
    decorative_mean = mean_quality(decorative)
    gap_random = promoted_mean - random_mean
    gap_decorative = promoted_mean - decorative_mean
    decorative_vs_random = decorative_mean - random_mean

    perm_rng = random.Random(PERMUTATION_SEED)
    n_ge = 0
    for _ in range(PERMUTATIONS):
        sample = perm_rng.sample(list(ideas), k)
        if mean_quality(sample) >= promoted_mean - 1e-12:
            n_ge += 1
    perm_rate = n_ge / float(PERMUTATIONS)

    if gap_random < MARGIN:
        print(
            f"FAILED:IMP-0339-probe2 bar did not beat random subset "
            f"promoted={promoted_mean:.3f} random={random_mean:.3f} gap={gap_random:.3f}"
        )
        return 1
    if gap_decorative < MARGIN:
        print(
            f"FAILED:IMP-0339-probe2 bar did not beat title-length decorative bar "
            f"promoted={promoted_mean:.3f} decorative={decorative_mean:.3f}"
        )
        return 1
    if decorative_vs_random >= MARGIN:
        print(
            f"FAILED:IMP-0339-probe2 title-length bar also beat random; "
            f"control does not discriminate decorative={decorative_mean:.3f} "
            f"random={random_mean:.3f}"
        )
        return 1
    if perm_rate >= 0.05:
        print(
            f"FAILED:IMP-0339-probe2 permutation rate {perm_rate:.3f} >= 0.05; "
            "random subsets of the same size match the promoted mean too often"
        )
        return 1

    decorative_ids = [i["idea_id"] for i in decorative]
    if set(decorative_ids) == set(promoted_ids):
        print("FAILED:IMP-0339-probe2 decorative bar selected the same set as the real bar")
        return 1

    payload = {
        "probe": "probe2-blind-quality",
        "unit_id": "IMP-0339",
        "k": k,
        "random_seed": RANDOM_SEED,
        "permutation_seed": PERMUTATION_SEED,
        "permutations": PERMUTATIONS,
        "margin": MARGIN,
        "promoted_mean": promoted_mean,
        "random_subset_mean": random_mean,
        "decorative_title_length_mean": decorative_mean,
        "gap_vs_random": gap_random,
        "gap_vs_decorative": gap_decorative,
        "decorative_minus_random": decorative_vs_random,
        "permutation_frac_ge_promoted": perm_rate,
        "random_subset_ids": [i["idea_id"] for i in random_subset],
        "decorative_ids": decorative_ids,
        "promoted_ids": promoted_ids,
        "blind": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"promoted_mean={promoted_mean:.3f} random_mean={random_mean:.3f} "
        f"decorative_mean={decorative_mean:.3f} perm_rate={perm_rate:.4f}"
    )
    print("SUCCESS:IMP-0339-probe2 promoted set beats random subset on blind rating")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
