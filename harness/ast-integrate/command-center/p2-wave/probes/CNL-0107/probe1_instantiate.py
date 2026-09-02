#!/usr/bin/env python3
"""Probe 1: instantiate CNL-0107 against a fixture task; nearest-sibling differential."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import instantiate as I  # noqa: E402


def main() -> int:
    task = I.load_task()
    ours = I.load_preset("preset_cnl0107.json")
    sibling = I.load_preset("preset_sibling_p08.json")
    catalog = I.load_preset("preset_catalog_class.json")

    inst = I.instantiate(ours, task)
    sib_inst = I.instantiate(sibling, task)
    cat_inst = I.instantiate(catalog, task)

    vs_p08 = I.profile_diff_axes(inst["profile"], sib_inst["profile"])
    vs_cat = I.profile_diff_axes(inst["profile"], cat_inst["profile"])

    ours_timeout = I.evaluate_stop(ours, I.timeout_without_coverage_state())
    ours_swapped = I.evaluate_stop(ours, I.timeout_without_coverage_state())
    sib_timeout = I.evaluate_stop(sibling, I.timeout_without_coverage_state())

    missing = [
        k
        for k in ("roster", "protocol_schedule", "voting_method", "stopping_expression")
        if not inst.get(k)
    ]
    ok = (
        not missing
        and len(inst["roster"]) >= 4
        and len(inst["protocol_schedule"]) >= 3
        and "timeout_outcome" in vs_p08
        and "voting_rule" in vs_p08
        and ours_timeout == "INCONCLUSIVE"
        and ours_swapped == "INCONCLUSIVE"
        and sib_timeout == "BLUE_WINS"
        and ours["id"] != sibling["id"]
        and len(vs_cat) > 0
    )
    payload = {
        "probe": "probe1-instantiate",
        "unit_id": "CNL-0107",
        "task_id": task["id"],
        "roster_role_ids": [r["role_id"] for r in inst["roster"]],
        "protocol_schedule_ids": [s["id"] for s in inst["protocol_schedule"]],
        "voting_method": inst["voting_method"],
        "stopping_expression": inst["stopping_expression"],
        "nearest_sibling": sibling["id"],
        "sibling_source": "reconstructed-from-catalog-cited-P08-red-blue-team",
        "axes_vs_p08": vs_p08,
        "axes_vs_catalog_class": vs_cat,
        "timeout_ours": ours_timeout,
        "timeout_sibling": sib_timeout,
        "budget_swap_still_inconclusive": ours_swapped == "INCONCLUSIVE",
        "library": I.library_present(),
        "pass": ok,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"roster={payload['roster_role_ids']} "
        f"schedule={payload['protocol_schedule_ids']} "
        f"vote={ours['voting']['rule']} "
        f"stop={ours['stopping']['timeout_outcome']} "
        f"sibling={sibling['id']} axes={vs_p08}"
    )
    if not ok:
        print("FAILED:CNL-0107-probe1 instantiate/sibling differential")
        return 1
    print("SUCCESS:CNL-0107-probe1 instantiate sibling-differential")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
