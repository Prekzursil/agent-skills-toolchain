#!/usr/bin/env python3
"""Probe 1: both-states per direction, detector-control, live two-count run.

Must fire on the bad fixture and be silent on the complete/restored fixture
for each direction. Must find a KNOWN orphan before treating a live zero as
real. Then re-run on the live tree and check FAILURE-MODES.json recorded
the same separate counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import live as L  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A2/FAILURE-MODES.json"


def main() -> int:
    ctrl = S.both_states()
    checks = [
        ("a_fires_on_delete", ctrl.get("a_fires_on_delete")),
        ("a_silent_on_complete", ctrl.get("a_silent_on_complete")),
        ("a_silent_on_restore", ctrl.get("a_silent_on_restore")),
        ("b_fires_on_unregistered", ctrl.get("b_fires_on_unregistered")),
        ("b_silent_on_complete", ctrl.get("b_silent_on_complete")),
        ("b_silent_on_restore", ctrl.get("b_silent_on_restore")),
        ("empty_file_is_direction_a", ctrl.get("empty_file_is_direction_a")),
        ("detector_control_a_found_known_orphan", ctrl.get("detector_control_a_found_known_orphan")),
        ("detector_control_b_found_known_orphan", ctrl.get("detector_control_b_found_known_orphan")),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:ARC-0012-probe1 {name}")
            return 1

    live = L.live_report(REPO)
    a = int(live["direction_a_orphan_registry_count"])
    b = int(live["direction_b_orphan_output_count"])
    print(f"live_direction_a={a} live_direction_b={b} fails_today={live['fails_today']}")
    if a < 1:
        print("FAILED:ARC-0012-probe1 live Direction A unexpectedly zero")
        return 1
    if b != 0:
        print("FAILED:ARC-0012-probe1 live Direction B unexpectedly non-zero")
        return 1
    # Detector-control already proved B can see a known orphan, so live B=0 is allowed.

    if not ART.is_file():
        print("FAILED:ARC-0012-probe1 FAILURE-MODES.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0012-probe1 self-declared {doc.get('state')}")
        return 1
    live_doc = doc.get("live_completeness") or {}
    if int(live_doc.get("direction_a_orphan_registry_count")) != a:
        print("FAILED:ARC-0012-probe1 artifact Direction A count drift")
        return 1
    if int(live_doc.get("direction_b_orphan_output_count")) != b:
        print("FAILED:ARC-0012-probe1 artifact Direction B count drift")
        return 1
    if "combined_consistent_count" in live_doc:
        print("FAILED:ARC-0012-probe1 combined count present")
        return 1
    if "SUCCESS:ARC-0012" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0012-probe1 sentinel absent")
        return 1
    print("SUCCESS:ARC-0012-probe1 both-states detector-control live two-counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
