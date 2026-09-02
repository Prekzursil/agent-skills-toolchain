#!/usr/bin/env python3
"""Probe 1: property test over 10,000 generated ids and roots.

Catalog tests_required[0] / evidence (a): every generated id and worktree
root length is <= the declared cap, and an over-cap input is refused.
A convention-only formatter (no enforce()) is shown to admit the same
input, proving the cap is a runtime check.
"""
from __future__ import annotations

import json
import random
import string
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import path_budget as PB  # noqa: E402

N = 10_000
SEED = 204
ALPHA = string.ascii_uppercase


def fail(msg: str) -> int:
    print(f"FAILED:TST-0204-probe1 {msg}")
    return 1


def main() -> int:
    caps = PB.declared_caps()
    id_cap = caps["MAX_UNIT_ID_LEN"]
    root_cap = caps["MAX_WORKTREE_NAME_LEN"]
    if id_cap < 7 or root_cap < id_cap:
        return fail(f"declared caps are not a budget: {caps}")

    src_flags = PB.caps_enforced_in_source()
    if not all(src_flags.values()):
        return fail(f"cap is not enforced in source {src_flags}")

    rng = random.Random(SEED)
    id_lengths: list[int] = []
    root_lengths: list[int] = []
    over_cap = 0
    for i in range(N):
        plen = rng.randint(2, 5)
        prefix = "".join(rng.choice(ALPHA) for _ in range(plen))
        serial = rng.randint(0, 9999)
        uid = PB.generate_unit_id(prefix, serial)
        leaf = PB.worktree_name(uid, shard=i % (PB._SHARD_MAX + 1))
        if len(uid) > id_cap or len(leaf) > root_cap:
            over_cap += 1
        id_lengths.append(len(uid))
        root_lengths.append(len(leaf))

    if over_cap:
        return fail(f"{over_cap}/{N} generated names exceeded a declared cap")
    if len(id_lengths) != N:
        return fail("property sample count drifted")

    # Both-states: in-cap id is returned; over-cap prefix is refused by name.
    ok_id = PB.generate_unit_id("TST", 204)
    if ok_id != "TST-0204" or len(ok_id) > id_cap:
        return fail(f"in-cap id drifted: {ok_id!r}")
    ok_leaf = PB.worktree_name(ok_id, shard=0)
    if len(ok_leaf) > root_cap:
        return fail(f"in-cap leaf drifted: {ok_leaf!r}")

    refused = False
    refuse_msg = ""
    try:
        PB.generate_unit_id("TOOLONG", 1)
    except PB.PathBudgetExceeded as exc:
        refused = True
        refuse_msg = str(exc)
    if not refused:
        return fail("over-cap prefix was accepted")
    if str(id_cap) not in refuse_msg and "cap" not in refuse_msg.lower():
        return fail(f"refusal did not name the cap: {refuse_msg!r}")

    mutant = PB.convention_only_unit_id("TOOLONG", 1)
    if len(mutant) <= id_cap:
        return fail(f"convention mutant was not over-cap: {mutant!r}")
    mutant_leaf = PB.convention_only_worktree_name("VERYLONGUNITID-0001", 0)
    if len(mutant_leaf) <= root_cap:
        return fail(f"convention leaf was not over-cap: {mutant_leaf!r}")
    try:
        PB.enforce("worktree_name", "x" * (root_cap + 1), root_cap)
        return fail("enforce() accepted an over-cap value")
    except PB.PathBudgetExceeded as exc:
        if str(root_cap) not in str(exc):
            return fail(f"enforce() refusal omitted cap: {exc}")

    payload = {
        "unit_id": "TST-0204",
        "probe": "probe1-property-ids",
        "pass": True,
        "n_generated": N,
        "seed": SEED,
        "caps": caps,
        "id_len_min": min(id_lengths),
        "id_len_max": max(id_lengths),
        "id_len_p100": max(id_lengths),
        "root_len_min": min(root_lengths),
        "root_len_max": max(root_lengths),
        "root_len_p100": max(root_lengths),
        "all_ids_at_or_under_cap": True,
        "all_roots_at_or_under_cap": True,
        "in_cap_id": ok_id,
        "in_cap_leaf": ok_leaf,
        "over_cap_refused": True,
        "refusal_names_cap": True,
        "refusal_message": refuse_msg,
        "convention_mutant_id": mutant,
        "convention_mutant_id_len": len(mutant),
        "convention_mutant_leaf": mutant_leaf,
        "convention_mutant_leaf_len": len(mutant_leaf),
        "source_enforcement": dict(src_flags),
        "hard_cap_not_convention": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"n={N} id_p100={payload['id_len_p100']}/{id_cap} "
        f"root_p100={payload['root_len_p100']}/{root_cap} "
        f"refused={refused} mutant_len={len(mutant)}"
    )
    print("SUCCESS:TST-0204-probe1 property test 10000 generated ids under cap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
