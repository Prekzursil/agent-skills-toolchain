#!/usr/bin/env python3
"""Probe 2: negative control — seat the same configuration twice; collision FIRES.

Starts from the tests, not the receipt narrative. Both-states:
  bad  = two seats, identical vendor+model+prompt+tools (tool order permuted)
  good = two seats, different prompts
Also requires the independence audit to reject the flagged pair's first rounds,
and a diverse pair to remain independent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0265-probe2 {msg}")
    return 1


def main() -> int:
    R = S.load_registry()

    bad = S.duplicate_pair_registry()
    bad_report = bad.collision_report()
    if not bad_report["fired"]:
        return fail("same configuration seated twice did not fire")
    if bad_report["effective_voice_count"] != 1:
        return fail(f"bad effective_voice_count={bad_report['effective_voice_count']} want=1")
    if bad_report["seat_count"] != 2:
        return fail(f"bad seat_count={bad_report['seat_count']}")

    a, b = bad.roster()
    if a.fingerprint != b.fingerprint:
        return fail("duplicate pair fingerprints diverged")
    if a.participant_id == b.participant_id:
        return fail("duplicate pair reused participant_id")
    if a.display_name == b.display_name:
        return fail("clone display_name collapsed; identity must remain distinct")
    if a.declared_expertise == b.declared_expertise:
        return fail("clone expertise collapsed; claimed expertise is not a voice")

    bad_audit = bad.independence_audit()
    if not bad_audit["all_flagged_pairs_non_independent"]:
        return fail(f"independence audit failed to reject clone pair {bad_audit}")
    if not bad_audit["pairs"][0]["first_round_identical"]:
        return fail("clone first-round briefs differed")

    good = S.diverse_pair_registry()
    good_report = good.collision_report()
    if good_report["fired"]:
        return fail("diverse pair constant-fired the collision detector")
    if good_report["effective_voice_count"] != 2:
        return fail(f"good effective_voice_count={good_report['effective_voice_count']}")
    g0, g1 = good.roster()
    good_audit = R.independence_audit(good.roster(), flagged_pairs=[(g0.participant_id, g1.participant_id)])
    if good_audit["pairs"][0]["independence_rejected"]:
        return fail("diverse pair first-round briefs were identical")

    prompt_split = S.same_model_different_prompt_registry().collision_report()
    if prompt_split["fired"]:
        return fail("same vendor+model different prompt fired as one voice")

    art = S.RECEIPT_PATH
    if not art.is_file():
        return fail("receipt missing")
    doc = json.loads(art.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0265" not in json.dumps(doc):
        return fail("sentinel absent")
    ncs = doc.get("negative_control_ids") or []
    if "IMP0265-NC-duplicate-config-fires" not in ncs:
        return fail("receipt omitted the duplicate-config negative control id")

    out = {
        "probe": "probe2-collision-negative",
        "unit_id": "IMP-0265",
        "pass": True,
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "bad_effective_voice_count": 1,
        "good_effective_voice_count": 2,
        "independence_rejected_on_clone": True,
        "independence_kept_on_diverse": True,
        "same_model_different_prompt_distinct": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0265-probe2 same-config collision fires; diverse pair silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
