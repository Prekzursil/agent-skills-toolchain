#!/usr/bin/env python3
"""Probe 1: both-states on the recognition (seat-share excess) channel.

FIRES on the captured-chair fixture, SILENT on the even-handed chair.
Also checks the design note names CAPTURE-BOUND-DUAL and records the same
partition the detector just computed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import capture as C  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0025-chair-powers-and-capture-resistance.md"
FIX_BAD = HERE / "fixtures" / "captured.json"
FIX_GOOD = HERE / "fixtures" / "evenhanded.json"
OUT = HERE / "probe1-both-states.raw.json"


def load_session(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0025-probe1 design note missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNL-0025-probe1 unparseable:{type(exc).__name__}")
        return 1
    if doc.get("unit_id") != "CNL-0025":
        print("FAILED:CNL-0025-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNL-0025" not in text:
        print("FAILED:CNL-0025-probe1 sentinel absent")
        return 1
    limit = (doc.get("structural_limit") or {}).get("id")
    if limit != C.LIMIT_ID:
        print(f"FAILED:CNL-0025-probe1 limit id {limit!r} != {C.LIMIT_ID!r}")
        return 1

    bad = C.detect(load_session(FIX_BAD))
    good = C.detect(load_session(FIX_GOOD))
    print(
        "negative_control captured-chair: "
        f"applicable={bad['applicable']} captured={bad['captured']} "
        f"channels_fired={bad['channels_fired']} "
        f"worst_excess={bad['recognition']['worst_excess']:.4f} "
        f"missing={bad['coverage']['missing_position_ids']}"
    )
    print(
        "evenhanded-chair: "
        f"applicable={good['applicable']} captured={good['captured']} "
        f"channels_fired={good['channels_fired']} "
        f"worst_excess={good['recognition']['worst_excess']:.4f} "
        f"missing={good['coverage']['missing_position_ids']}"
    )
    if not bad["applicable"] or not bad["captured"] or not bad["recognition"]["fires"]:
        print("FAILED:CNL-0025-probe1 captured-chair did not fire recognition channel")
        return 1
    if not good["applicable"] or good["captured"] or good["recognition"]["fires"]:
        print("FAILED:CNL-0025-probe1 even-handed chair tripped the bound")
        return 1

    recorded = doc.get("both_states") or {}
    rec_bad = recorded.get("captured") or {}
    rec_good = recorded.get("evenhanded") or {}
    if rec_bad.get("captured") is not True or rec_good.get("captured") is not False:
        print("FAILED:CNL-0025-probe1 artifact both_states does not match live partition")
        return 1
    if abs(float(rec_bad.get("worst_excess") or 0) - float(bad["recognition"]["worst_excess"])) > 1e-9:
        print("FAILED:CNL-0025-probe1 recorded worst_excess drifted from live detector")
        return 1

    payload = {
        "probe": "probe1-both-states-recognition",
        "unit_id": "CNL-0025",
        "fired_on_captured": True,
        "silent_on_evenhanded": True,
        "captured_channels": bad["channels_fired"],
        "evenhanded_channels": good["channels_fired"],
        "captured_worst_excess": bad["recognition"]["worst_excess"],
        "evenhanded_worst_excess": good["recognition"]["worst_excess"],
        "pass": True,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SUCCESS:CNL-0025-probe1 captured fires, even-handed silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
