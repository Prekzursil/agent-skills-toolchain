#!/usr/bin/env python3
"""Probe 1: instantiate both incident-lifecycle presets against a fixture task."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preset as P  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0108-probe1 {msg}")
    return 1


def main() -> int:
    task = P.load_task()
    family = P.family_presets()
    if len(family) != 2:
        return fail(f"expected 2 family members, got {len(family)}")
    live, retro = family
    if live["id"] != "C-IL-LIVE" or retro["id"] != "C-IL-RETRO":
        return fail("family member ids drifted")

    inst_live = P.instantiate(live, task)
    inst_retro = P.instantiate(retro, task)
    print(
        json.dumps(
            {
                "task_id": task["id"],
                "live": inst_live,
                "retrospective": inst_retro,
            },
            sort_keys=True,
        )
    )

    for label, inst, src in (
        ("live", inst_live, live),
        ("retro", inst_retro, retro),
    ):
        if not inst["roster"] or not inst["protocol_schedule"]:
            return fail(f"{label} missing roster or schedule")
        if inst["voting_method"] != src["voting"]["method"]:
            return fail(f"{label} voting not taken from preset")
        if inst["stopping_expression"] != src["stopping"]["expr"]:
            return fail(f"{label} stopping not taken from preset")

    intra = P.axis_diffs(live, retro)
    print(f"intra_family_axes={intra} distance={len(intra)}")
    required_intra = {
        "clock",
        "floor_may_skip",
        "voting",
        "evidence_order",
        "protocols",
        "roster",
    }
    missing = sorted(required_intra - set(intra))
    if missing:
        return fail(f"family members share load-bearing axes {missing}")

    who = P.who_may_skip(family)
    print(f"may_skip={who['may_skip']} must_hold={who['must_hold_floor']}")
    if who["may_skip"] != ["C-IL-LIVE"]:
        return fail("only C-IL-LIVE may skip the floor")
    if "C-IL-RETRO" not in who["must_hold_floor"]:
        return fail("C-IL-RETRO must hold the floor")

    early = {
        "rounds": 1,
        "independent_briefs": 1,
        "evidence_items": 0,
        "containment_declared": True,
        "elapsed_minutes": 14,
        "mitigation_in_place": True,
        "each_why_has_evidence": True,
        "competing_hypotheses_scored": True,
        "action": "containment",
    }
    live_contain = P.apply_floor(live, early)
    retro_contain = P.apply_floor(retro, {**early, "action": "causal-verdict"})
    live_causal = P.apply_floor(live, {**early, "action": "causal-verdict"})
    print(
        json.dumps(
            {
                "live_containment_unmet_floor": live_contain,
                "retro_unmet_floor": retro_contain,
                "live_causal_unmet_floor": live_causal,
            },
            sort_keys=True,
        )
    )
    if not live_contain["stop"] or not live_contain["floor_skip_used"]:
        return fail("live containment must skip unmet floor")
    if retro_contain["stop"] or not retro_contain["floor_blocked"]:
        return fail("retrospective must block satisfied stop under unmet floor")
    if live_causal["stop"] or not live_causal["floor_blocked"]:
        return fail("live must not skip floor for a causal verdict")

    hang_state = {
        "rounds": live["floor_policy"]["ceiling_max_rounds"],
        "independent_briefs": 0,
        "evidence_items": 0,
        "action": "containment",
        "containment_declared": False,
        "elapsed_minutes": 0,
        "mitigation_in_place": False,
    }
    hang = P.apply_floor(live, hang_state)
    print(f"ceiling hung={hang['hung']} audit={hang['audit']}")
    if not hang["hung"]:
        return fail("floor with no ceiling would hang; ceiling must fire")

    print("SUCCESS:CNL-0108-probe1 instantiate floor-skip differential")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
