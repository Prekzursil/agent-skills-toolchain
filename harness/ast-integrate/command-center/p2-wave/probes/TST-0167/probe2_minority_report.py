#!/usr/bin/env python3
"""Probe 2 (independent reviewer): minority-report survival + dissent-drop seed.

Does not import probe1. Re-runs suspend/resume live and checks:
  * uninterrupted council dissent == suspend-then-resume dissent
  * pre-suspend minority entries are a subset of the final transcript section
  * dropping dissent from the checkpoint is detected (regression seed)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import council_fixture_runtime as R  # noqa: E402

ART = REPO / "command-center/receipts/TST-0167.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0167-probe2 {msg}")
    return 1


def main() -> int:
    live = R.live()
    if not live.get("both_states_same_dissent"):
        return fail("uninterrupted dissent content != resumed dissent content")
    if not live.get("both_states_same_rounds"):
        return fail("uninterrupted rounds != resumed rounds")
    if not live.get("both_states_same_transcript"):
        return fail(
            f"uninterrupted sha {live.get('uninterrupted_sha256')} "
            f"!= resumed sha {live.get('resumed_sha256')}"
        )
    if not live.get("pre_survived_in_final"):
        return fail("pre-suspend minority entries missing from final minority-report")
    if live.get("pre_minority_count", 0) < 1:
        return fail("pre-suspend minority is empty")
    if live.get("dissenters_uninterrupted") != ["critic"]:
        return fail(f"expected critic dissent, got {live.get('dissenters_uninterrupted')}")
    if live.get("dissenters_resumed") != live.get("dissenters_uninterrupted"):
        return fail("resumed dissenters drifted")

    neg = live.get("negative_control") or {}
    if not neg.get("fired_on_bad_state"):
        return fail(f"dissent-drop mutation was silent: {neg}")
    if not neg.get("silent_on_good_state"):
        return fail("preservation check fired on the good checkpoint")
    if neg.get("error_type") != "DissentDropped":
        return fail(f"unexpected drop error_type {neg.get('error_type')}")
    if live.get("model_calls") != 0:
        return fail(f"model_calls={live.get('model_calls')} want 0")

    print(
        f"uninterrupted={live.get('uninterrupted_sha256')} "
        f"resumed={live.get('resumed_sha256')} "
        f"pre_min={live.get('pre_minority_sha256')} "
        f"final_min={live.get('final_minority_sha256')} "
        f"drop={neg.get('message')}"
    )

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec_m = doc.get("minority") or {}
        if rec_m.get("pre_sha256") != live.get("pre_minority_sha256"):
            return fail("receipt minority.pre_sha256 != live")
        if rec_m.get("final_sha256") != live.get("final_minority_sha256"):
            return fail("receipt minority.final_sha256 != live")
        if rec_m.get("pre_survived_in_final") is not True:
            return fail("receipt does not record pre-suspend minority survival")
        rec_b = doc.get("both_states") or {}
        if rec_b.get("uninterrupted_sha256") != live.get("uninterrupted_sha256"):
            return fail("receipt uninterrupted sha != live")
        if rec_b.get("resumed_sha256") != live.get("resumed_sha256"):
            return fail("receipt resumed sha != live")
        rec_n = doc.get("negative_control") or {}
        if rec_n.get("fired_on_bad_state") is not True:
            return fail("receipt negative_control.fired_on_bad_state is not true")
        if rec_n.get("silent_on_good_state") is not True:
            return fail("receipt negative_control.silent_on_good_state is not true")
        reviewer = doc.get("reviewer") or {}
        if reviewer.get("independent") is not True:
            return fail("receipt reviewer.independent is not true")
        if reviewer.get("verdict") not in {"PASS", "CONFIRMED"}:
            return fail(f"receipt reviewer.verdict={reviewer.get('verdict')}")
        print("receipt minority, both-states and drop-mutation match live")

    print("SUCCESS:TST-0167-probe2 minority-report survival and dissent-drop detection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
