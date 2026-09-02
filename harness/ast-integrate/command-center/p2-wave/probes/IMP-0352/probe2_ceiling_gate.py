#!/usr/bin/env python3
"""Probe 2: over-ceiling fixture refuses; removing the gate lets it launch."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools" / "council" / "cli"))

import runtime as RT  # noqa: E402
from corpus import launch_spec, over_ceiling_fixture, under_ceiling_for  # noqa: E402
from tools.council.budget.preflight import (  # noqa: E402
    GATE_REFUSE_ALLOWED,
    REASON_CEILING_BREACH,
    REASON_GATE_ABSENT,
    REASON_OWNER_WAIVER,
    REASON_UNDER_CEILING,
    OwnerApproval,
    preflight,
)

PREFLIGHT_PATH = REPO / "tools" / "council" / "budget" / "preflight.py"
MARKER = "GATE_REFUSE_ALLOWED = False  # IMP-0352-GATE-REFUSE"
MUTANT_LINE = "GATE_REFUSE_ALLOWED = True  # IMP-0352-GATE-REFUSE"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0352-probe2 {msg}")
    return 1


def event_kinds(result: RT.CouncilResult) -> list[str]:
    return [e.get("kind") for e in result.events]


def main() -> int:
    if GATE_REFUSE_ALLOWED:
        return fail("live GATE_REFUSE_ALLOWED is True")
    src = PREFLIGHT_PATH.read_text(encoding="utf-8")
    if src.count(MARKER) != 1:
        return fail(f"refuse marker count={src.count(MARKER)}")

    plan, ceiling, estimate = over_ceiling_fixture()
    live = preflight(plan, ceiling)
    if live.allowed or live.launched:
        return fail("live over-ceiling launched")
    if live.reason != REASON_CEILING_BREACH:
        return fail(f"live reason={live.reason}")
    if not live.breaches:
        return fail("live over-ceiling reported no breaches")

    under = preflight(plan, under_ceiling_for(plan))
    if not under.allowed or under.reason != REASON_UNDER_CEILING:
        return fail(f"under-ceiling {under.allowed} {under.reason}")

    absent = preflight(plan, ceiling, apply_gate=False)
    if not absent.allowed or not absent.launched:
        return fail("gate-absent did not launch")
    if absent.reason != REASON_GATE_ABSENT:
        return fail(f"gate-absent reason={absent.reason}")
    if not absent.breaches:
        return fail("gate-absent hid the breaches it would have caught")

    reviewer = OwnerApproval(
        granted=True, approver_id="reviewer", ticket="NOT-OWNER", dimensions=()
    )
    spoofed = preflight(plan, ceiling, reviewer)
    if spoofed.allowed:
        return fail("reviewer impersonation granted a waiver")

    owner = OwnerApproval(
        granted=True,
        approver_id="owner-alice",
        ticket="BUDGET-WAIVER-0352",
        dimensions=("tokens", "wall_clock_seconds", "external_calls"),
    )
    waived = preflight(plan, ceiling, owner)
    if not waived.allowed or waived.reason != REASON_OWNER_WAIVER:
        return fail(f"owner waiver {waived.allowed} {waived.reason}")

    mutant_src = src.replace(MARKER, MUTANT_LINE, 1)
    if mutant_src == src:
        return fail("mutant source identical to live")
    ns: dict = {}
    exec(compile(mutant_src, "<imp0352-mutant>", "exec"), ns)
    mutant = ns["preflight"](plan, ceiling)
    if not mutant.allowed:
        return fail("mutant still refused over-ceiling (negative control did not fire)")
    if PREFLIGHT_PATH.read_text(encoding="utf-8") != src:
        return fail("live preflight.py mutated on disk")

    no_ceiling = {
        "id": "imp0352-no-ceiling",
        "participants": [
            {"id": "a", "vote": "yes"},
            {"id": "b", "vote": "yes"},
        ],
        "voting": {"rule": "majority", "quorum": 2},
    }
    launched = RT.execute(no_ceiling)
    if not launched.ok:
        return fail(f"no-ceiling spec failed to launch: {launched.reason}")
    if "vote" not in event_kinds(launched):
        return fail("no-ceiling launch produced no vote events")

    refused = RT.execute(launch_spec(over_ceiling=True))
    if refused.ok:
        return fail("execute launched an over-ceiling spec")
    if refused.reason != REASON_CEILING_BREACH:
        return fail(f"execute reason={refused.reason}")
    kinds = event_kinds(refused)
    if "vote" in kinds:
        return fail(f"over-ceiling execute still voted: {kinds}")
    if "preflight-refuse" not in kinds:
        return fail(f"over-ceiling execute events={kinds}")

    ok_ceiling = RT.execute(launch_spec(over_ceiling=False))
    if not ok_ceiling.ok or "vote" not in event_kinds(ok_ceiling):
        return fail("under-ceiling execute did not launch")

    waived_run = RT.execute(
        launch_spec(
            over_ceiling=True,
            approval={
                "granted": True,
                "approver_id": "owner-alice",
                "ticket": "BUDGET-WAIVER-0352",
                "dimensions": ["tokens", "wall_clock_seconds", "external_calls"],
            },
        )
    )
    if not waived_run.ok or "vote" not in event_kinds(waived_run):
        return fail("owner-waived over-ceiling execute did not launch")

    payload = {
        "pass": True,
        "probe": "probe2-ceiling-gate",
        "unit_id": "IMP-0352",
        "live_allowed": live.allowed,
        "live_reason": live.reason,
        "live_breaches": list(live.breaches),
        "estimate": estimate.as_dict(),
        "ceiling": ceiling.as_dict(),
        "gate_absent_allowed": absent.allowed,
        "gate_absent_reason": absent.reason,
        "mutant_allowed": mutant.allowed,
        "reviewer_spoof_allowed": spoofed.allowed,
        "owner_waiver_allowed": waived.allowed,
        "execute_over_ceiling_ok": refused.ok,
        "execute_over_ceiling_events": kinds,
        "execute_no_ceiling_ok": launched.ok,
        "source_unchanged": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "live_launch=False mutant_launch=True gate_absent=True "
        "execute_over_ceiling=refused source_unchanged=True"
    )
    print(
        "SUCCESS:IMP-0352-probe2 over-ceiling refuses; "
        "removing the gate lets it launch"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
