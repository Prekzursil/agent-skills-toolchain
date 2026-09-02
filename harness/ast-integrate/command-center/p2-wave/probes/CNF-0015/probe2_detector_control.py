#!/usr/bin/env python3
"""Probe 2: detector control + decision-log second half.

Mechanically different from probe 1:
  * plant one bare M-07 on the post-fix tree and require the collision test
    to FIRE (proves the detector is not hardcoded to the pre-fix fixture)
  * require silence on the unmodified post-fix tree
  * measure 17-DECISION-LOG: zero MECH tokens AND present-tense collision
    on the stale fixture; silent after reconcile (both-states for half 2)
  * schema must reject three garbage documents
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import collision_test as C  # noqa: E402
import decision_log as D  # noqa: E402
import scenario as S  # noqa: E402
import schema_check as SC  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0015-blocker-repro.json"
SCHEMA = REPO / "command-center/schema/repro-report.schema.json"


def main() -> int:
    files = S.write_fixtures()

    rc_good, good = C.run(files["option"], files["arch_post"])
    rc_planted, planted = C.run(files["option"], files["arch_planted"])
    print(
        json.dumps(
            {
                "post_fix_exit": rc_good,
                "post_fix_shared": good["shared_count"],
                "planted_exit": rc_planted,
                "planted_shared": planted["shared_count"],
                "planted_ids": planted["shared_ids"],
            },
            sort_keys=True,
        )
    )
    if rc_good != 0 or good["shared_count"] != 0:
        print("FAILED:CNF-0015-probe2 post-fix was not silent")
        return 1
    if rc_planted != 1 or "M-07" not in planted["shared_ids"]:
        print("FAILED:CNF-0015-probe2 planted M-07 did not fire the detector")
        return 1
    if planted["shared_count"] < 1:
        print("FAILED:CNF-0015-probe2 planted shared_count is 0")
        return 1

    stale = D.analyze(files["log_stale"])
    recon = D.analyze(files["log_reconciled"])
    print(json.dumps({"stale": stale, "reconciled": recon}, sort_keys=True)[:4000])
    if stale["mech_token_count"] != 0:
        print(
            f"FAILED:CNF-0015-probe2 stale log MECH count={stale['mech_token_count']}"
        )
        return 1
    if not stale["present_tense_collision"]:
        print("FAILED:CNF-0015-probe2 stale log missing present-tense collision")
        return 1
    if not stale["stale_present_tense_with_zero_mech"]:
        print("FAILED:CNF-0015-probe2 stale dual-condition did not fire")
        return 1
    if recon["stale_present_tense_with_zero_mech"]:
        print("FAILED:CNF-0015-probe2 reconciled log still fires staleness")
        return 1
    if recon["mech_token_count"] < 1:
        print("FAILED:CNF-0015-probe2 reconciled log has no MECH token")
        return 1
    if stale["stale_present_tense_with_zero_mech"] == recon["stale_present_tense_with_zero_mech"]:
        print("FAILED:CNF-0015-probe2 decision-log both-states are not opposite")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0015-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    domain = SC.domain(doc)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0015-probe2 self-declared {doc.get('state')}")
        return 1
    dl = domain.get("decision_log") or {}
    if int(dl.get("stale", {}).get("mech_token_count", -1)) != 0:
        print("FAILED:CNF-0015-probe2 artifact MECH count drift")
        return 1
    if dl.get("stale", {}).get("present_tense_collision") is not True:
        print("FAILED:CNF-0015-probe2 artifact present-tense flag drift")
        return 1
    ctrl = domain.get("detector_control") or {}
    if ctrl.get("fired_on_planted_m07") is not True:
        print("FAILED:CNF-0015-probe2 artifact detector_control missing fire")
        return 1
    if ctrl.get("silent_on_post_fix") is not True:
        print("FAILED:CNF-0015-probe2 artifact detector_control missing silence")
        return 1

    if not SCHEMA.is_file():
        print("FAILED:CNF-0015-probe2 schema missing")
        return 1
    ok, notes = SC.rejects_garbage()
    for n in notes:
        print(n)
    if not ok:
        print("FAILED:CNF-0015-probe2 schema accepted garbage")
        return 1
    errs = SC.errors(domain)
    if errs:
        print(f"FAILED:CNF-0015-probe2 artifact schema invalid: {errs[0]}")
        return 1

    print("SUCCESS:CNF-0015-probe2 detector-control and decision-log both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
