#!/usr/bin/env python3
"""Named probe 1: seat-for-seat reproducibility from the recorded seed.

Required test: unit: reproducibility from seed.

Both directions are asserted because same-seed identity alone cannot detect a
frozen sampler (CNL-0016): same seed -> identical roster AND different seed ->
different roster. A fresh-entropy run must still replay from its recorded seed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.participants.select_random import (  # noqa: E402
    reproduce,
    roster_matches,
    select_stratified,
    select_uniform,
)
from pool import (  # noqa: E402
    REQUESTED_STRATA,
    SEED_A,
    SEED_B,
    UNIFORM_K,
    build_pool,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0270-probe1 {msg}")
    return 1


def main() -> int:
    pool = build_pool()
    u1 = select_uniform(pool, UNIFORM_K, seed=SEED_A)
    u2 = select_uniform(pool, UNIFORM_K, seed=SEED_A)
    u_other = select_uniform(pool, UNIFORM_K, seed=SEED_B)
    if not roster_matches(u1, u2):
        return fail("uniform same-seed rosters differ")
    if u1["roster_ids"] != u2["roster_ids"]:
        return fail("uniform same-seed roster_ids differ")
    if u1["seed"] != SEED_A or u2["seed"] != SEED_A:
        return fail("uniform did not record the caller seed")
    if roster_matches(u1, u_other):
        return fail("uniform different-seed rosters identical (frozen sampler)")
    u_replay = reproduce(u1, pool)
    if not roster_matches(u1, u_replay):
        return fail("uniform reproduce() from recorded seed diverged")

    s1 = select_stratified(pool, REQUESTED_STRATA, seed=SEED_A)
    s2 = select_stratified(pool, REQUESTED_STRATA, seed=SEED_A)
    s_other = select_stratified(pool, REQUESTED_STRATA, seed=SEED_B)
    if not roster_matches(s1, s2):
        return fail("stratified same-seed rosters differ")
    if s1["seed"] != SEED_A:
        return fail("stratified did not record the caller seed")
    if roster_matches(s1, s_other):
        return fail("stratified different-seed rosters identical (frozen sampler)")
    if s1["stratum_census"] != REQUESTED_STRATA:
        return fail(f"stratified census {s1['stratum_census']} != {REQUESTED_STRATA}")
    s_replay = reproduce(s1, pool)
    if not roster_matches(s1, s_replay):
        return fail("stratified reproduce() from recorded seed diverged")

    fresh = select_uniform(pool, UNIFORM_K, seed=None)
    if fresh["seed_source"] != "fresh-entropy":
        return fail("omitted seed was not marked fresh-entropy")
    if fresh["seed"] is None:
        return fail("fresh-entropy run did not record a seed")
    fresh_replay = reproduce(fresh, pool)
    if not roster_matches(fresh, fresh_replay):
        return fail("fresh-entropy run was not reproducible from its recorded seed")

    # Seat-for-seat is ordered: set equality would hide a permutation bug.
    if set(s1["roster_ids"]) == set(s_other["roster_ids"]) and s1["roster_ids"] == s_other["roster_ids"]:
        # Same people AND same order across seeds is the frozen-sampler case
        # already rejected above. If we got here, lists already differ.
        pass
    if len(s1["roster_ids"]) != len(set(s1["roster_ids"])):
        return fail("stratified roster seated a participant twice")

    summary = {
        "fresh_entropy_recorded_seed": fresh["seed"],
        "fresh_replay_match": True,
        "pass": True,
        "probe": "probe1-reproducibility",
        "stratified_other_ids": s_other["roster_ids"],
        "stratified_roster_ids": s1["roster_ids"],
        "stratified_same_seed_match": True,
        "uniform_other_ids": u_other["roster_ids"],
        "uniform_roster_ids": u1["roster_ids"],
        "uniform_same_seed_match": True,
        "unit_id": "IMP-0270",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "same_seed_match=True different_seed_differs=True "
        f"uniform={u1['roster_ids']} stratified={s1['roster_ids']} "
        f"fresh_replay=True seed={u1['seed']}"
    )
    print("SUCCESS:IMP-0270-probe1 reproducibility from recorded seed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
