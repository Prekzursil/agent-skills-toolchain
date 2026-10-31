#!/usr/bin/env python3
"""Probe 2: mid-operation partition - partial survival and resume (mechanically
different from probe 1: two-step operation with the cut between step 1 and
step 2, scratch-dir persistence, not the offline cache table).

Naive loses the in-flight partial and restarts from zero; the contract client
keeps the step-1 bytes on disk, degrades explicitly at the cut, and a resume
completes the artifact without dropping step 1. Fixture is loopback-only.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
from common import (  # noqa: E402
    REPO as R,
    SENTINEL,
    UNIT_ID,
    fail,
)

ART = R / "command-center/adversarial/ADV-0128-offline-and-partition-degrade-loudly.json"


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix=f"{UNIT_ID.lower()}-p2-"))
    live = E.run_partition(root)
    printable = {
        "probe": "probe2-mid-partition",
        "unit_id": UNIT_ID,
        "pass": bool(
            live["explicit_step2_all"]
            and live["naive_lost_all"]
            and live["contract_kept_all"]
            and live["contract_resume_all"]
        ),
        "fixture_loopback_only": True,
        "explicit_step2_all": live["explicit_step2_all"],
        "naive_lost_all": live["naive_lost_all"],
        "contract_kept_all": live["contract_kept_all"],
        "contract_resume_all": live["contract resume_all".replace(" ", "_")],
        "rows": live["rows"],
    }
    print(json.dumps(printable, sort_keys=True))
    if not live["explicit_step2_all"]:
        return fail("step 2 through the cut did not fail explicitly on all paths")
    if not live["naive_lost_all"]:
        return fail("naive client did not lose its in-flight partial")
    if not live["contract_kept_all"]:
        return fail("contract step-1 bytes did not survive the cut")
    if not live["contract_resume_all"]:
        return fail("contract resume did not complete without dropping step 1")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("catalog sentinel absent")
    pc = doc.get("partition_campaign") or {}
    art_rows = pc.get("rows") or []
    if len(art_rows) != len(live["rows"]):
        return fail("artifact partition row count drifted")
    for ar in art_rows:
        p = ar.get("path_id")
        if not ar.get("after_cut_contract_has_step1"):
            return fail(f"artifact row {p}: contract step-1 not kept")
        cn = ar.get("cut_naive") or {}
        if not (cn.get("restarted_from_zero") and not cn.get("partial_kept")):
            return fail(f"artifact row {p}: naive restart-from-zero not recorded")

    controls = pc.get("controls") or {}
    if not (
        controls.get("contract_partial_survives_partition")
        and controls.get("contract_resume_completes_without_dropping_step1")
        and controls.get("naive_loses_partial_on_partition")
    ):
        return fail("artifact partition controls incomplete")
    print(
        f"SUCCESS:{UNIT_ID}-probe2 mid-partition lost naive partial x4; "
        "contract kept step-1 and resumed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
