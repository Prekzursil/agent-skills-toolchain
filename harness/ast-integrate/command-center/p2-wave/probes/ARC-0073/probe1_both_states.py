#!/usr/bin/env python3
"""Probe 1: both-states, extraction-control, live designs, artifact drift."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import live as L  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/CONTROL-PLANE-SINGULARITY.json"


def main() -> int:
    ctrl = S.both_states()
    checks = [
        ("singular_ok", ctrl.get("singular_ok")),
        ("duplicate_fails", ctrl.get("duplicate_fails")),
        ("duplicate_prose_ignored", ctrl.get("duplicate_prose_ignored")),
        ("hybrid_fixture_singular", ctrl.get("hybrid_fixture_singular")),
        ("extraction_found_known_row", ctrl.get("extraction_found_known_row")),
        ("pass", ctrl.get("pass")),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:ARC-0073-probe1 {name}")
            return 1
    print(f"duplicate_authority_count={ctrl.get('duplicate_authority_count')}")
    if int(ctrl.get("duplicate_authority_count") or 0) < 2:
        print("FAILED:ARC-0073-probe1 planted duplicate did not extract two authorities")
        return 1

    live = L.report(REPO)
    ext = live["extraction_control"]
    print(f"a1_present={ext.get('a1_present')} a1_known_skill_found={ext.get('a1_known_skill_found')}")
    print(f"a1_singular_trusted={ext.get('a1_singular_trusted')}")
    print(f"a2_present={ext.get('a2_present')} a2_ssot_found={ext.get('a2_ssot_found')}")
    print(f"a2_singular_trusted={ext.get('a2_singular_trusted')}")
    print(f"fixture_known_skill_found={ext.get('fixture_known_skill_found')}")
    print(f"ranking_present={live.get('ranking_present')} a9_present={live.get('a9_present')}")
    if ext.get("a1_present"):
        if not ext.get("a1_known_skill_found") or not ext.get("a1_singular_trusted"):
            print("FAILED:ARC-0073-probe1 A1 extraction-control")
            return 1
    elif not ext.get("fixture_known_skill_found") or not ext.get("fixture_singular"):
        print("FAILED:ARC-0073-probe1 fixture extraction-control")
        return 1
    if ext.get("a2_present"):
        if not ext.get("a2_ssot_found") or not ext.get("a2_singular_trusted"):
            print("FAILED:ARC-0073-probe1 A2 extraction-control")
            return 1
    print(f"live_design_count={len(live['live_designs'])}")
    for d in live["live_designs"]:
        print(
            f"live {d['architecture_id']} singular={d['singular']} "
            f"rows={d['row_count']} dups={d['duplicate_count']}"
        )
        if not d["singular"]:
            print(f"FAILED:ARC-0073-probe1 live {d['architecture_id']} not singular")
            return 1

    if not ART.is_file():
        print("FAILED:ARC-0073-probe1 CONTROL-PLANE-SINGULARITY.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0073-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0073" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0073-probe1 sentinel absent")
        return 1
    bs = doc.get("both_states") or {}
    if not bs.get("duplicate_fails") or not bs.get("singular_passes"):
        print("FAILED:ARC-0073-probe1 artifact both-states drift")
        return 1
    if int(bs.get("duplicate_authority_count") or 0) != int(ctrl["duplicate_authority_count"]):
        print("FAILED:ARC-0073-probe1 artifact duplicate authority count drift")
        return 1
    inputs = doc.get("inputs_on_disk") or {}
    if bool(inputs.get("ranking_present")) != bool(live.get("ranking_present")):
        print("FAILED:ARC-0073-probe1 ranking presence drift")
        return 1
    if bool(inputs.get("a9_present")) != bool(live.get("a9_present")):
        print("FAILED:ARC-0073-probe1 a9 presence drift")
        return 1
    print("SUCCESS:ARC-0073-probe1 both-states extraction-control live designs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
