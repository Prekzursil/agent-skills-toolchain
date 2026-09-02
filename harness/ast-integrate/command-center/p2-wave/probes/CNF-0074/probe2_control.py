#!/usr/bin/env python3
"""Probe 2: change-one-input control + detector control on known-broken fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import battery as B  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0074-workflow-replay-determinism.json"
SENTINEL = (
    "SUCCESS:CNF-0074 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and the change-one-input control "
    "produced a different artifact, ruling out cache-driven false identity. Any "
    "other terminal state is FAILED:CNF-0074 <classification> with the diagnostic "
    "tail attached."
)


def main() -> int:
    ctrl = B.change_one_input_control()
    print(
        f"change_one_input artifacts_differ={ctrl['artifacts_differ']} "
        f"cache_masking_ruled_out={ctrl['cache_masking_ruled_out']} "
        f"changed={ctrl['changed_input']}"
    )
    if not ctrl["performed"]:
        print("FAILED:CNF-0074-probe2 control was not performed")
        return 1
    if not ctrl["artifacts_differ"]:
        print("FAILED:CNF-0074-probe2 change-one-input produced identical artifacts")
        return 1
    if not ctrl["cache_masking_ruled_out"]:
        print("FAILED:CNF-0074-probe2 cache masking was not ruled out")
        return 1
    if ctrl["baseline_sha256"] == ctrl["mutated_sha256"]:
        print("FAILED:CNF-0074-probe2 sha256 did not change after input mutation")
        return 1

    broken = B.broken_cache_detector()
    print(f"broken_cache_detector fired={broken['fired']} {broken['reason']}")
    if not broken["fired"]:
        print("FAILED:CNF-0074-probe2 known-broken id-only cache did not fire")
        return 1

    oc = B.overclaim_detector()
    print(
        f"overclaim_detector fired={oc['fired']} verdict={oc.get('verdict')} "
        f"paths={oc.get('semantic_paths')}"
    )
    if not oc["fired"]:
        print("FAILED:CNF-0074-probe2 known-broken overclaim fixture did not fire")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0074-probe2 confirmation artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0074-probe2 sentinel absent")
        return 1
    live_ctrl = doc.get("change_one_input_control") or {}
    if live_ctrl.get("artifacts_differ") is not True:
        print("FAILED:CNF-0074-probe2 artifact control.artifacts_differ is not true")
        return 1
    if live_ctrl.get("cache_masking_ruled_out") is not True:
        print("FAILED:CNF-0074-probe2 artifact did not record cache-masking ruled out")
        return 1
    if not (doc.get("overclaims") or []):
        print("FAILED:CNF-0074-probe2 artifact filed no overclaims")
        return 1
    print("SUCCESS:CNF-0074-probe2 change-one-input and detector-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
