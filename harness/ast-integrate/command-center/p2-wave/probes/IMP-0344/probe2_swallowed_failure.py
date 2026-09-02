#!/usr/bin/env python3
"""Probe 2: negative control — swallowed council failure must not pass.

Both-states:
  * a planted event log with an unclassified council.turn.failed fires the detector
  * a classified honest failure is silent
  * a SwallowingInvoker run through the live bridge is classified under the
    workflow failure policy (family=swallowed-failure) and does not silently pass
  * an honest CouncilFailed classifies as model-error/abort from the workflow policy
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0344.json"


def main() -> int:
    detector = S.run_detector_both_states()
    swallow = S.run_swallowed_through_bridge()
    honest = S.run_honest_failure()
    print(
        json.dumps(
            {
                "detector_both_states": detector,
                "swallowed_through_bridge": swallow,
                "honest_failure": honest,
            },
            sort_keys=True,
            default=str,
        )[:4000]
    )
    if not detector["ok"]:
        print(
            "FAILED:IMP-0344-probe2 detector did not discriminate "
            f"fired_on_bad={detector.get('fired_on_bad')} "
            f"silent_on_good={detector.get('silent_on_good')}"
        )
        return 1
    if not swallow["ok"] or swallow.get("silent_pass"):
        print("FAILED:IMP-0344-probe2 swallowing invoker silently passed")
        return 1
    classified = swallow.get("classified") or {}
    if classified.get("family") != "swallowed-failure":
        print(f"FAILED:IMP-0344-probe2 swallow classified as {classified}")
        return 1
    if classified.get("source") != "workflow.failure_policy":
        print(f"FAILED:IMP-0344-probe2 swallow source {classified.get('source')}")
        return 1
    if not honest["ok"]:
        print("FAILED:IMP-0344-probe2 honest council failure not classified from workflow policy")
        return 1
    hon = honest.get("classified") or {}
    if hon.get("family") != "model-error" or hon.get("action") != "abort":
        print(f"FAILED:IMP-0344-probe2 honest classification {hon}")
        return 1
    if hon.get("source") != "workflow.failure_policy":
        print(f"FAILED:IMP-0344-probe2 honest source {hon.get('source')}")
        return 1
    if honest.get("swallowed_count") != 0:
        print("FAILED:IMP-0344-probe2 honest path still looks swallowed")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0344-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0344" not in text:
        print("FAILED:IMP-0344-probe2 sentinel absent")
        return 1
    print(
        "fired_on_bad=True silent_on_good=True "
        "swallow_classified=swallowed-failure honest_classified=model-error/abort"
    )
    print("SUCCESS:IMP-0344-probe2 swallowed-failure negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
