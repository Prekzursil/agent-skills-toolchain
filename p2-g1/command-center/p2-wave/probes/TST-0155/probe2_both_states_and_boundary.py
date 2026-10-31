#!/usr/bin/env python3
"""Probe 2: both-states (no rotation), mid-line boundary, negative controls.

Mechanically different from probe 1: no-rotation count equality, a rotate
that splits a line, and two known-broken readers that must fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0155.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0155-probe2 {msg}")
    return 1


def main() -> int:
    H._wipe_runtime()
    none = H.no_rotation_control(H.FollowReader)
    mid = H.mid_line_rotation(H.FollowReader)
    stuck = H.negative_stuck_fd()
    recount = H.negative_recount()
    printable = {
        "no_rotation_pass": none["pass"],
        "no_rotation_count": none["monitor_count"],
        "no_rotation_offline": none["offline_count"],
        "no_rotation_rotated_exists": none["rotated_exists"],
        "mid_pass": mid["pass"],
        "mid_lines": mid["monitor_lines"],
        "mid_offline": mid["offline_lines"],
        "mid_crashed": mid["crashed"],
        "stuck_fired": stuck["fired_on_bad_state"],
        "stuck_count": stuck["monitor_count"],
        "stuck_offline": stuck["offline_count"],
        "recount_fired": recount["fired_on_bad_state"],
        "recount_count": recount["monitor_count"],
        "recount_offline": recount["offline_count"],
        "recount_recounts": recount["recounts"],
        "expected_total": H.N1 + H.N2,
    }
    print(json.dumps(printable, sort_keys=True))
    if not none["pass"]:
        return fail("no-rotation control did not match offline count")
    if none["monitor_count"] != H.N1 + H.N2:
        return fail("no-rotation count drifted")
    if none["rotated_exists"]:
        return fail("no-rotation unexpectedly created a rotated file")
    if not mid["pass"]:
        return fail(
            f"mid-line monitor={mid['monitor_lines']} "
            f"offline={mid['offline_lines']} crash={mid['crash_exc']}"
        )
    if mid["monitor_lines"] != ["HEAD-TAIL"]:
        return fail(f"mid-line split or recap: {mid['monitor_lines']}")
    if not stuck["fired_on_bad_state"]:
        return fail(
            f"stuck-fd negative silent count={stuck['monitor_count']} "
            f"offline={stuck['offline_count']}"
        )
    if not recount["fired_on_bad_state"]:
        return fail(
            f"recount negative silent count={recount['monitor_count']} "
            f"offline={recount['offline_count']} recaps={recount['recounts']}"
        )
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared {doc.get('state')}")
        nc = doc.get("negative_controls") or []
        fired = [c.get("fired_on_bad_state") for c in nc if isinstance(c, dict)]
        if fired and not all(fired):
            return fail("artifact negative_controls not all fired")
        both = doc.get("both_states") or {}
        if both and both.get("same_count") is not True:
            return fail("artifact both_states.same_count is not true")
    print(
        "SUCCESS:TST-0155-probe2 both-states+mid-line "
        f"stuck_fired={stuck['fired_on_bad_state']} "
        f"recount_fired={recount['fired_on_bad_state']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
