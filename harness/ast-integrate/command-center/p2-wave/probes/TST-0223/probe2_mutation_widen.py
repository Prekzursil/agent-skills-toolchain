#!/usr/bin/env python3
"""Probe 2: AST-mutate narrow() intersection into union; property must go red."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
import scenario as S  # noqa: E402

if str(C.SPEC_ROOT) not in sys.path:
    sys.path.insert(0, str(C.SPEC_ROOT))

from agentspec.permission_bound import (  # noqa: E402
    SEED,
    narrow,
    run_property_corpus,
)


def fail(msg: str) -> int:
    print(f"FAILED:{C.UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    snapshot = S.bound_source_snapshot()
    if not S.live_narrow_is_intersection():
        return fail("live narrow() is not an intersection")

    live = run_property_corpus(n_trees=400, seed=SEED, narrow_fn=narrow)
    if not live["pass"] or live["violations"] != 0:
        return fail(f"live control red: {live['violations']}")

    mutant = S.mutate_narrow_bitand_to_bitor()
    parent = frozenset({"Read"})
    declared = frozenset({"Read", "Write"})
    if mutant(parent, declared) != frozenset({"Read", "Write"}):
        return fail(f"mutant did not union: {sorted(mutant(parent, declared))}")
    if narrow(parent, declared) != frozenset({"Read"}):
        return fail("live narrow drifted")

    mutated = run_property_corpus(n_trees=400, seed=SEED, narrow_fn=mutant)
    if mutated["violations"] < 1 or mutated["pass"] is True:
        return fail(
            "union mutant kept the property green; "
            f"violations={mutated['violations']}"
        )
    if mutated["widening_calls_allowed"] < 1:
        return fail("union mutant never allowed a widening privileged call")

    if S.bound_source_snapshot() != snapshot:
        return fail("permission_bound.py bytes changed")
    relive = run_property_corpus(n_trees=200, seed=SEED, narrow_fn=narrow)
    if not relive["pass"]:
        return fail("live corpus drifted after mutant exec")

    payload = {
        "probe": "probe2-mutation-widen",
        "unit_id": C.UNIT,
        "live_violations": live["violations"],
        "mutant_violations": mutated["violations"],
        "mutant_widening_calls_allowed": mutated["widening_calls_allowed"],
        "mutant_property": "RED",
        "source_unchanged": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"live_violations={live['violations']} "
        f"mutant_violations={mutated['violations']} "
        f"mutant_widening_allowed={mutated['widening_calls_allowed']} "
        "property_on_mutant=RED source_unchanged=True"
    )
    print(
        "SUCCESS:TST-0223-probe2 mutation: union-widen turns "
        "child_perms subset parent_perms red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
