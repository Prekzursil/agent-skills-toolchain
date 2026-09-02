#!/usr/bin/env python3
"""Probe 1: 100% canary catch on a pipeline-produced bundle, scan command recorded."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import suite as S  # noqa: E402

ART = REPO / "command-center/phase3/A7/TEST-PLAN.json"


def main() -> int:
    live = S.run_suite()
    canary = live["canary"]
    if canary["catch_rate"] != 1.0 or not canary["caught"]:
        print("FAILED:ARC-0050-probe1 canary catch was not 100%")
        print(json.dumps(canary, indent=2, default=str)[:3000])
        return 1
    if not canary["silent_on_clean"]:
        print("FAILED:ARC-0050-probe1 clean pipeline bundle was not silent")
        return 1
    if not canary["plant"]["pipeline_produced"] or canary["plant"]["synthetic_file"]:
        print("FAILED:ARC-0050-probe1 canary was not planted in a pipeline bundle")
        return 1
    if int(canary["member_count"] or 0) < 4:
        print("FAILED:ARC-0050-probe1 bundle is too small to be a real package")
        return 1
    if "C14-secret-gate" not in (canary["scan_clean"].get("subchecks_run") or []):
        print("FAILED:ARC-0050-probe1 publisher conform did not run C14 secret-gate")
        return 1
    cmd = canary["scan_command"]
    if "conform" not in cmd or "astplugin" not in cmd:
        print("FAILED:ARC-0050-probe1 scan command not recorded")
        return 1
    if canary["canary"].get("prefix") != "sk-ant-":
        print("FAILED:ARC-0050-probe1 canary prefix drift")
        return 1
    if '"_token"' in json.dumps(canary):
        print("FAILED:ARC-0050-probe1 canary value leaked into the report")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec = (doc.get("report") or {}).get("canary") or doc.get("canary") or {}
        if rec.get("catch_rate") != 1.0:
            print("FAILED:ARC-0050-probe1 artifact catch_rate is not 1.0")
            return 1
        if "SUCCESS:ARC-0050" not in json.dumps(doc):
            print("FAILED:ARC-0050-probe1 artifact sentinel missing")
            return 1
        if rec.get("scan_command") != canary["scan_command"]:
            print("FAILED:ARC-0050-probe1 artifact scan_command drift")
            return 1
        if rec.get("planted_in_pipeline_bundle") is not True:
            print("FAILED:ARC-0050-probe1 artifact did not record pipeline plant")
            return 1

    out = {
        "probe": "probe1-canary-catch",
        "unit_id": "ARC-0050",
        "catch_rate": canary["catch_rate"],
        "silent_on_clean": canary["silent_on_clean"],
        "member_count": canary["member_count"],
        "plant_member": canary["plant"]["member"],
        "scan_command": canary["scan_command"],
        "prefix": canary["canary"]["prefix"],
        "token_sha256": canary["canary"]["token_sha256"],
        "packer": canary["packer"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "canary_catch=1.0 silent_clean=True "
        f"members={canary['member_count']} packer={canary['packer']}"
    )
    print("SUCCESS:ARC-0050-probe1 canary catch on pipeline bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
