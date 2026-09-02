#!/usr/bin/env python3
"""Probe 1: instantiate the live preset and name the nearest sibling."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import instantiate, nearest_sibling  # noqa: E402
from preset import PRESET  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0106-code-review-tribunal-backed-by-an-executable-oracle.md"
)
EXPECTED_SIBLING = "C-cited:P46-architecture-review-board"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0106-probe1 {msg}")
    return 1


def main() -> int:
    live_path = REPO / OUT
    if not live_path.is_file():
        return fail("artifact-absent")
    live = json.loads(live_path.read_text(encoding="utf-8"))
    if live.get("id") != PRESET["id"]:
        return fail("live-preset-id-mismatch")
    if "SUCCESS:CNL-0106" not in live_path.read_text(encoding="utf-8"):
        return fail("sentinel-absent")

    task_code = json.loads(
        (HERE / "fixtures/task_code.json").read_text(encoding="utf-8")
    )
    task_test = json.loads(
        (HERE / "fixtures/task_test.json").read_text(encoding="utf-8")
    )
    inst_code = instantiate(PRESET, task_code)
    inst_test = instantiate(PRESET, task_test)

    roster = inst_code["roster"]
    schedule = [s["id"] for s in inst_code["protocol_schedule"]]
    voting = inst_code["voting"]
    stopping = inst_code["stopping"]
    if inst_code["voting_seats"] != [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic",
    ]:
        return fail(f"code-roster {inst_code['voting_seats']}")
    if "TestBinder" not in [s["role_id"] for s in roster]:
        return fail("TestBinder-unseated-on-code")
    if "EvidenceClerk" in [s["role_id"] for s in roster]:
        return fail("EvidenceClerk-seated-on-code")
    if "oracle-gate" not in schedule or "P50" in schedule:
        return fail(f"code-schedule {schedule}")
    if voting.get("rule") != "majority":
        return fail("voting-rule")
    if "bound_oracle_fail→NOT-YES" not in str(stopping.get("expression") or ""):
        return fail("stopping-expression")

    test_roles = [s["role_id"] for s in inst_test["roster"]]
    test_sched = [s["id"] for s in inst_test["protocol_schedule"]]
    if "EvidenceClerk" not in test_roles:
        return fail("EvidenceClerk-absent-on-test-subject")
    if "P50" not in test_sched:
        return fail(f"test-schedule-missing-P50 {test_sched}")
    if inst_code["protocol_schedule"] == inst_test["protocol_schedule"]:
        return fail("code-and-test-schedules-identical")
    if inst_code["roster"] == inst_test["roster"]:
        return fail("code-and-test-rosters-identical")

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
    oracle_diff = [
        d
        for d in sib["measurable_diffs"]
        if d["field"] == "fail_overrides_majority"
        and d["preset"] is True
        and d["sibling"] is False
    ]
    if not oracle_diff:
        return fail("oracle-differential-absent")
    if not sib["measurable_diffs"]:
        return fail("name-only-differential")

    planted = json.loads(json.dumps(siblings[0]))
    planted["id"] = "PLANTED-RENAME-OF-P46"
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
                "unit_id": "CNL-0106",
                "task": inst_code["task_id"],
                "roster": inst_code["roster"],
                "protocol_schedule": inst_code["protocol_schedule"],
                "voting": voting,
                "stopping": stopping,
                "test_subject_roster": inst_test["roster"],
                "test_subject_schedule": inst_test["protocol_schedule"],
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
        f"SUCCESS:CNL-0106-probe1 instantiate roster={inst_code['voting_seats']} "
        f"sibling={sib['id']} distance={sib['distance']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
