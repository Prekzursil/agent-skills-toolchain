#!/usr/bin/env python3
"""Named probe 2: decompose round-trip + loss control (both-states).

Good state: recovered components run standalone and the capability
difference is empty. Bad state: drop the cite stage (unique LicenseScan)
and the difference must name that capability. A detector silent on the
dropped stage is a detector failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_forge.decompose import (  # noqa: E402
    capability_report,
    decompose,
    drop_stage,
    fuse_and_record,
    run_standalone,
)
import fixtures as F  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0317-probe2 {msg}")
    return 1


def main() -> int:
    srcs = F.sources()
    cases = F.cases()
    fusion = fuse_and_record(srcs, F.evidence())
    if not fusion.get("ok"):
        return fail(f"fusion refused {fusion}")

    good_caps = fusion["capability_report"]
    if not good_caps["empty_difference"]:
        return fail(f"good fusion already lossy {good_caps['difference']}")

    dec = decompose(fusion)
    if not dec["ok"] or len(dec["components"]) != 2:
        return fail(f"decompose {dec}")

    standalone = []
    for sid, component in dec["components"].items():
        run = run_standalone(component, cases[0])
        if not run.get("ok"):
            return fail(f"recovered {sid} standalone {run}")
        if not run.get("produced"):
            return fail(f"recovered {sid} produced no stage output")
        standalone.append(
            {
                "source_id": sid,
                "stages_run": [p["stage"] for p in run["produced"]],
                "ok": True,
            }
        )

    dropped = drop_stage(fusion["workflow"], "cite")
    if any(_id(st) == "cite" for st in dropped.get("stages") or []):
        return fail("drop_stage left cite in place")
    bad_caps = capability_report(srcs, dropped)
    if bad_caps["empty_difference"] or not bad_caps["blocking_finding"]:
        return fail(f"dropping cite was silent {bad_caps}")
    lost = set(bad_caps["difference"])
    if "stage:cite" not in lost:
        return fail(f"difference did not name stage:cite {sorted(lost)}")
    if "tool:LicenseScan" not in lost:
        return fail(f"difference did not name tool:LicenseScan {sorted(lost)}")

    if good_caps["blocking_finding"] or not bad_caps["blocking_finding"]:
        return fail("both-states failed: detector not discriminating")

    payload = {
        "probe": "probe2-decompose-and-loss",
        "unit_id": "TST-0317",
        "silent_on_good": True,
        "fired_on_dropped_cite": True,
        "lost": sorted(lost),
        "standalone": standalone,
        "recovered_ids": dec["recovered_ids"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "silent_on_good=True fired_on_dropped_cite=True "
        f"lost={sorted(lost)} standalone_ok=True"
    )
    print(
        "SUCCESS:TST-0317-probe2 recovered components run standalone; "
        "dropping cite is detected as capability loss"
    )
    return 0


def _id(stage: dict) -> str:
    return str(stage.get("id") or "")


if __name__ == "__main__":
    raise SystemExit(main())
