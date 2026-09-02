#!/usr/bin/env python3
"""Probe 1 (signal a): structural diff of pre-suspend vs post-restore council state.

Re-runs suspend + restore live. Round index, per-round votes, confidence
trajectory, idea/objection sets, phase, and minority-report sha must match.
If a receipt exists, its recorded hashes must equal this live pair.
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
    print(f"FAILED:TST-0167-probe1 {msg}")
    return 1


def main() -> int:
    live = R.live()
    if not live.get("structural_match"):
        return fail("pre-suspend structural state != post-restore structural state")
    pre = live.get("structural_pre") or {}
    restored = live.get("structural_restored") or {}
    for key in (
        "round_index",
        "phase",
        "idea_ids",
        "objection_ids",
        "per_round_votes",
        "confidence_trajectory",
    ):
        if pre.get(key) != restored.get(key):
            return fail(f"structural field {key} drifted across restore")
    if pre.get("round_index") != live.get("after_round"):
        return fail(
            f"round_index={pre.get('round_index')} want after_round={live.get('after_round')}"
        )
    pre_min = (pre.get("minority_report") or {}).get("sha256")
    rest_min = (restored.get("minority_report") or {}).get("sha256")
    if not pre_min or pre_min != rest_min:
        return fail(f"minority sha pre={pre_min} restored={rest_min}")
    if (pre.get("minority_report") or {}).get("count", 0) < 1:
        return fail("pre-suspend minority report is empty")
    if live.get("model_calls") != 0:
        return fail(f"model_calls={live.get('model_calls')} want 0")

    print(
        f"after_round={live.get('after_round')} "
        f"round_index={pre.get('round_index')} "
        f"phase={pre.get('phase')} "
        f"pre_minority={pre_min} "
        f"votes={pre.get('per_round_votes')}"
    )

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec = doc.get("structural") or {}
        if rec.get("match") is not True:
            return fail("receipt structural.match is not true")
        if rec.get("pre_minority_sha256") != pre_min:
            return fail("receipt pre_minority_sha256 != live")
        if rec.get("restored_minority_sha256") != rest_min:
            return fail("receipt restored_minority_sha256 != live")
        if rec.get("after_round") != live.get("after_round"):
            return fail("receipt after_round != live")
        print("receipt structural hashes match live pair")

    print("SUCCESS:TST-0167-probe1 structural pre-suspend vs post-restore identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
