#!/usr/bin/env python3
"""Probe 1: instantiate family presets and name the nearest sibling."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def main() -> int:
    family = E.family_members()
    siblings = E.sibling_presets()
    task = E.fixture_task()
    brainstorm = E.by_id(family, E.BRAINSTORM_ID)
    moonshot = E.by_id(family, E.MOONSHOT_ID)

    inst_b = E.instantiate(brainstorm, task)
    inst_m = E.instantiate(moonshot, task)
    assert inst_b["roster"], "brainstorm roster empty"
    assert inst_m["roster"], "moonshot roster empty"
    assert inst_b["protocol_schedule"], "brainstorm schedule empty"
    assert inst_m["protocol_schedule"], "moonshot schedule empty"
    assert inst_b["voting_method"] != inst_m["voting_method"]
    assert inst_b["stopping_expression"] != inst_m["stopping_expression"]
    assert inst_b["weighting"] != inst_m["weighting"]
    assert inst_b["accept_rule"] != inst_m["accept_rule"]
    assert inst_b["ranking_key"] != inst_m["ranking_key"]
    assert inst_b["weighting"]["novelty"] < inst_m["weighting"]["novelty"]
    assert inst_b["weighting"]["feasibility"] > inst_m["weighting"]["feasibility"]

    sib_b, dist_b, fields_b = E.nearest_sibling(brainstorm, siblings)
    sib_m, dist_m, fields_m = E.nearest_sibling(moonshot, siblings)
    assert dist_b >= 1, f"brainstorm collapsed into {sib_b['id']}"
    assert dist_m >= 1, f"moonshot collapsed into {sib_m['id']}"
    assert sib_b["id"], "unnamed sibling"
    assert sib_m["id"], "unnamed sibling"

    clone = E.name_only_clone(
        brainstorm, "C-G26-100-idea-brainstorm-RENAMED", "moonshot in name only"
    )
    clone_rejected = False
    try:
        E.reject_if_duplicate(clone, brainstorm)
    except E.MechanismDuplicate:
        clone_rejected = True
    assert clone_rejected, "name-only clone was not rejected"

    bad_task = {
        "id": "task.illegal-vote-override",
        "overrides": {"voting.method": "majority"},
    }
    override_rejected = False
    try:
        E.instantiate(brainstorm, bad_task)
    except E.NonEditableOverride as exc:
        override_rejected = str(exc) == "voting.method"
    assert override_rejected, "non-editable override was accepted"

    gaming = E.gaming_ledger()
    genuine = E.genuine_ledger(100)
    assert len(gaming) == 100
    assert len(E.unique_ideas(gaming)) == 10
    assert len(E.unique_ideas(genuine)) == 100
    assert E.stop_fires(brainstorm, gaming) is False
    assert E.stop_fires(brainstorm, genuine, completeness=0.95) is True
    assert E.stop_fires(moonshot, gaming) is False
    assert E.stop_fires(moonshot, genuine) is True
    thin = E.by_id(siblings, "C-G26-thin")
    assert E.stop_fires(thin, gaming) is True, "thin sibling must fire on raw count"

    print(
        json.dumps(
            {
                "brainstorm_id": inst_b["preset_id"],
                "moonshot_id": inst_m["preset_id"],
                "brainstorm_roster": inst_b["roster"],
                "moonshot_roster": inst_m["roster"],
                "brainstorm_schedule": [
                    s["protocol_id"] for s in inst_b["protocol_schedule"]
                ],
                "moonshot_schedule": [
                    s["protocol_id"] for s in inst_m["protocol_schedule"]
                ],
                "brainstorm_vote": inst_b["voting_method"],
                "moonshot_vote": inst_m["voting_method"],
                "brainstorm_stop": inst_b["stopping_expression"],
                "moonshot_stop": inst_m["stopping_expression"],
                "brainstorm_nearest_sibling": sib_b["id"],
                "brainstorm_sibling_distance": dist_b,
                "brainstorm_differing_fields": fields_b,
                "moonshot_nearest_sibling": sib_m["id"],
                "moonshot_sibling_distance": dist_m,
                "moonshot_differing_fields": fields_m,
                "name_only_clone_rejected": True,
                "gaming_unique": len(E.unique_ideas(gaming)),
                "genuine_unique": len(E.unique_ideas(genuine)),
                "brainstorm_stop_on_gaming": False,
                "brainstorm_stop_on_genuine": True,
            },
            indent=2,
        )
    )
    print("SUCCESS:CNL-0103-probe1 instantiate-and-sibling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
