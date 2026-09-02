#!/usr/bin/env python3
"""Probe 2: independent reviewer re-runs the detector control.

Confirms (1) platform-conditional skips are not lumped with unconditional
ones, (2) the comparison is executed count, not passed count. Does not read
probe 1's verdict as evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from skip_diff import payload_from_receipt, run_planted_skip_control, skip_sets  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0060-skip-count-diff.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0060-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0060":
        print("FAILED:CNF-0060-probe2 unit_id", doc.get("unit_id"))
        return 1

    ctrl = run_planted_skip_control()
    after_kinds = skip_sets(ctrl["after"])["by_skip_kind"]
    uncond = list(after_kinds.get("unconditional") or [])
    plat = list(after_kinds.get("platform-conditional") or [])
    disabled = ctrl["disabled"]
    payload = {
        "probe": "probe2-reviewer-control",
        "unit_id": "CNF-0060",
        "pass": False,
        "unconditional_skips": uncond,
        "platform_conditional_skips": plat,
        "kinds_disjoint": ctrl["kinds_distinct"],
        "executed_before": disabled["executed_count_before"],
        "executed_after": disabled["executed_count_after"],
        "passed_before": disabled["passed_count_before"],
        "passed_after": disabled["passed_count_after"],
        "passed_count_unchanged": disabled["passed_count_unchanged"],
        "executed_count_dropped": disabled["executed_count_dropped"],
        "control_fired": ctrl["fired"],
    }

    ok = (
        ctrl["fired"]
        and ctrl["kinds_distinct"]
        and bool(uncond)
        and bool(plat)
        and set(uncond).isdisjoint(set(plat))
        and disabled["executed_count_dropped"]
        and disabled["passed_count_unchanged"]
        and disabled["executed_count_after"] == disabled["executed_count_before"] - 1
    )
    payload["pass"] = bool(ok)
    print(json.dumps(payload, sort_keys=True))
    if not uncond or not plat:
        print("FAILED:CNF-0060-probe2 missing skip-kind buckets", after_kinds)
        return 1
    if not ctrl["kinds_distinct"]:
        print("FAILED:CNF-0060-probe2 platform-conditional collapsed into unconditional")
        return 1
    if not disabled["passed_count_unchanged"]:
        print("FAILED:CNF-0060-probe2 expected passed count unchanged (failing test skipped)")
        return 1
    if not disabled["executed_count_dropped"]:
        print("FAILED:CNF-0060-probe2 executed count did not drop; detector compared the wrong thing")
        return 1
    if not ctrl["fired"]:
        print("FAILED:CNF-0060-probe2 independent control did not fire")
        return 1
    art_ctrl = payload_from_receipt(doc)["planted_skip"]
    if art_ctrl.get("kinds_distinct") is not True:
        print("FAILED:CNF-0060-probe2 artifact missing kinds_distinct")
        return 1
    print(
        "unconditional",
        uncond,
        "platform-conditional",
        plat,
        "executed",
        disabled["executed_count_before"],
        "->",
        disabled["executed_count_after"],
        "passed",
        disabled["passed_count_before"],
        "==",
        disabled["passed_count_after"],
    )
    print("SUCCESS:CNF-0060-probe2 skip kinds distinct; executed count compared, not passed count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
