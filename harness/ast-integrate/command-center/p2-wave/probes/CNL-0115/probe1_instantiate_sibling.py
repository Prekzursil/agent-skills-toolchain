#!/usr/bin/env python3
"""Probe 1: instantiate the live preset and name the nearest sibling."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import ACK_UNCHANGED, instantiate, nearest_sibling  # noqa: E402
from fixtures import task_delta, task_stale_six_weeks  # noqa: E402
from preset import PRESET  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0115-standing-watch-council-long-running-trigger-woken-low-inte.md"
)
EXPECTED_SIBLING = "C-cited:P51-timeboxed-spike-council"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0115-probe1 {msg}")
    return 1


def main() -> int:
    live_path = REPO / OUT
    if not live_path.is_file():
        return fail("artifact-absent")
    text = live_path.read_text(encoding="utf-8")
    live = json.loads(text)
    if live.get("id") != PRESET["id"]:
        return fail("live-preset-id-mismatch")
    if "SUCCESS:CNL-0115" not in text:
        return fail("sentinel-absent")

    stale = task_stale_six_weeks()
    delta = task_delta()
    inst_sleep = instantiate(PRESET, stale)
    inst_wake = instantiate(PRESET, delta)

    sleep_roles = [s["role_id"] for s in inst_sleep["roster"]]
    if sleep_roles != ["WatchClerk", "Archivist", "DutySentinel"]:
        return fail(f"sleep-roster {sleep_roles}")
    if inst_sleep["voting_seats"]:
        return fail(f"sleep-voting-seats {inst_sleep['voting_seats']}")
    if inst_sleep["classified"]["disposition"] != ACK_UNCHANGED:
        return fail(f"stale-disposition {inst_sleep['classified']['disposition']}")
    if "wake-deliberate" in [s["id"] for s in inst_sleep["protocol_schedule"]]:
        return fail("sleep-schedule-seated-panel")
    if inst_sleep["voting"].get("rule") != "majority":
        return fail("voting-rule")
    expr = str(inst_sleep["stopping"].get("expression") or "")
    if "stale_fp→ACK-UNCHANGED" not in expr:
        return fail("stopping-expression")

    wake_roles = [s["role_id"] for s in inst_wake["roster"]]
    if "Chair" not in wake_roles or "Skeptic" not in wake_roles:
        return fail(f"wake-roster {wake_roles}")
    if inst_wake["voting_seats"] != ["Chair", "Skeptic", "Pragmatist"]:
        return fail(f"wake-voting {inst_wake['voting_seats']}")
    wake_sched = [s["id"] for s in inst_wake["protocol_schedule"]]
    if "wake-deliberate" not in wake_sched or "lineage-bind" not in wake_sched:
        return fail(f"wake-schedule {wake_sched}")
    if inst_sleep["protocol_schedule"] == inst_wake["protocol_schedule"]:
        return fail("sleep-and-wake-schedules-identical")
    if inst_sleep["roster"] == inst_wake["roster"]:
        return fail("sleep-and-wake-rosters-identical")

    siblings = json.loads((HERE / "siblings.json").read_text(encoding="utf-8"))[
        "presets"
    ]
    sib = nearest_sibling(PRESET, siblings)
    if sib["id"] != EXPECTED_SIBLING:
        return fail(f"nearest-sibling {sib['id']}")
    live_sib = str((live.get("nearest_sibling") or {}).get("id") or "")
    if live_sib != EXPECTED_SIBLING:
        return fail(f"live-nearest-sibling {live_sib}")
    if sib["distance"] <= 0:
        return fail("zero-distance-duplicate")
    load_bearing = [
        d
        for d in sib["measurable_diffs"]
        if d["field"] in {"trigger_woken", "sleep_default", "settled_ledger"}
        and d["preset"] is True
        and d["sibling"] is False
    ]
    if len(load_bearing) < 3:
        return fail(f"watch-differential-absent {sib['measurable_diffs']}")
    if not sib["measurable_diffs"]:
        return fail("name-only-differential")

    planted = json.loads(json.dumps(siblings[0]))
    planted["id"] = "PLANTED-RENAME-OF-P51"
    planted_rank = nearest_sibling(planted, siblings)
    if planted_rank["id"] != EXPECTED_SIBLING or planted_rank["distance"] != 0:
        return fail(
            f"planted-rename-not-caught id={planted_rank['id']} "
            f"d={planted_rank['distance']}"
        )

    print(
        json.dumps(
            {
                "probe": "probe1-instantiate-sibling",
                "unit_id": "CNL-0115",
                "task": inst_sleep["task_id"],
                "roster": inst_sleep["roster"],
                "protocol_schedule": inst_sleep["protocol_schedule"],
                "voting": inst_sleep["voting"],
                "stopping": inst_sleep["stopping"],
                "wake_roster": inst_wake["roster"],
                "wake_schedule": inst_wake["protocol_schedule"],
                "nearest_sibling": sib["id"],
                "distance": sib["distance"],
                "measurable_diffs": [d["field"] for d in sib["measurable_diffs"]],
                "planted_rename_caught": True,
                "pass": True,
            },
            indent=2,
        )
    )
    print(
        f"SUCCESS:CNL-0115-probe1 instantiate roster={sleep_roles} "
        f"sibling={sib['id']} distance={sib['distance']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
