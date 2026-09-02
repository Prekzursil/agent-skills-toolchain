#!/usr/bin/env python3
"""Probe 1: detector control before any zero-collision census is trusted.

Plant a Name/name pair and assert the detector finds it. A clean schema
must stay silent. Then re-run the live census and require the artifact to
record the same fingerprint.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import report as R  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0101.json"


def main() -> int:
    control = D.run_control()
    print(
        "control fired="
        f"{control.get('fired')} clean_silent={control.get('clean_silent')} "
        f"trusted={control.get('trusted')} order={control.get('order')}"
    )
    if not control.get("fired"):
        print("FAILED:ARC-0101-probe1 planted Name/name pair was not detected")
        return 1
    if not control.get("clean_silent"):
        print("FAILED:ARC-0101-probe1 clean schema produced a collision or duplicate")
        return 1
    if control.get("order") != "control-before-census":
        print("FAILED:ARC-0101-probe1 control order not recorded")
        return 1

    live = R.measured()
    fp = live["fingerprint"]
    print(
        "census files_parsed="
        f"{fp['files_parsed']} same_object_collisions="
        f"{fp['same_object_case_collision_count']} named_present="
        f"{fp['named_contracts_present']}"
    )
    if not ART.is_file():
        print("FAILED:ARC-0101-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0101-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0101" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0101-probe1 sentinel absent")
        return 1
    body = R.artifact_payload(doc)
    art_ctrl = body.get("detector_control") or {}
    if art_ctrl.get("fired") is not True or art_ctrl.get("clean_silent") is not True:
        print("FAILED:ARC-0101-probe1 artifact detector_control did not record both-states")
        return 1
    art_fp = body.get("fingerprint") or {}
    for key in (
        "same_object_case_collision_count",
        "files_parsed",
        "named_contracts_present",
        "detector_control_fired",
    ):
        if art_fp.get(key) != fp.get(key):
            print(f"FAILED:ARC-0101-probe1 fingerprint mismatch {key}: art={art_fp.get(key)} live={fp.get(key)}")
            return 1
    if not (body.get("schema_census") or {}).get("generated_from_schema_files"):
        print("FAILED:ARC-0101-probe1 census was not generated from schema files")
        return 1
    if fp["files_parsed"] < 1:
        print("FAILED:ARC-0101-probe1 no live schema files parsed")
        return 1
    print("SUCCESS:ARC-0101-probe1 detector-control before census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
