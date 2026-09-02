#!/usr/bin/env python3
"""IMP-0129 probe 2: cyclic fixture fails with closed id; namespace mutant goes red."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentspec" / "tests"))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from agentspec.validate import VIOLATION_SUBWORKFLOW_CYCLE  # noqa: E402
from test_subworkflow import (  # noqa: E402
    check_cyclic_fails_acyclic_passes,
    check_namespace_mutation_collision_goes_red,
)


def main() -> int:
    cycle = check_cyclic_fails_acyclic_passes()
    mutant = check_namespace_mutation_collision_goes_red()
    payload = {
        "probe": "probe2-cycle-and-namespace-mutation",
        "unit_id": "IMP-0129",
        "pass": bool(cycle["pass"] and mutant["pass"]),
        "violation_id": VIOLATION_SUBWORKFLOW_CYCLE,
        "cycle": cycle,
        "mutation": mutant,
        "both_states": {
            "bad_fires": cycle.get("pass") and VIOLATION_SUBWORKFLOW_CYCLE in cycle.get("cyclic_ids", []),
            "good_silent": cycle.get("acyclic_ids") == [],
        },
        "id_collision_test_live": mutant.get("live_unique"),
        "id_collision_test_mutant_goes_red": mutant.get("mutant_unique") is False,
        "walk_calls": cycle.get("walk_calls"),
        "walk_depth": cycle.get("walk_depth"),
    }
    print(json.dumps(payload, sort_keys=True))
    if not cycle["pass"]:
        print("FAILED:IMP-0129-probe2 cyclic/acyclic both-states or unbounded walk")
        return 1
    if not mutant["pass"]:
        print("FAILED:IMP-0129-probe2 deleting namespacing did not redden id-collision test")
        return 1
    print(
        "SUCCESS:IMP-0129-probe2 cycle id subworkflow-reference-cycle bounded; "
        "namespace mutation reddens collision test"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
