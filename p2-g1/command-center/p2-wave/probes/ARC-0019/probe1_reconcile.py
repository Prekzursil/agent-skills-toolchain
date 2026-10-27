#!/usr/bin/env python3
"""Probe 1: both-states, planted-orphan negative control, live disagreement.

Must fire on the bad fixture and go silent on the complete/restored fixture
for each direction. Must find a planted unregistered install before treating
a live Direction-B zero as real. Then re-run on the live tree and check
FAILURE-MODES.json recorded the same separate counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import live as L  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A3/FAILURE-MODES.json"


def main() -> int:
    ctrl = S.both_states()
    checks = [
        ("a_fires_on_missing_install", ctrl.get("a_fires_on_missing_install")),
        ("a_silent_on_complete", ctrl.get("a_silent_on_complete")),
        ("a_silent_on_restore", ctrl.get("a_silent_on_restore")),
        ("b_fires_on_planted_orphan", ctrl.get("b_fires_on_planted_orphan")),
        ("b_silent_on_complete", ctrl.get("b_silent_on_complete")),
        ("b_silent_on_restore", ctrl.get("b_silent_on_restore")),
        ("empty_package_is_registry_not_deployed", ctrl.get("empty_package_is_registry_not_deployed")),
        ("detector_control_a_found_known_orphan", ctrl.get("detector_control_a_found_known_orphan")),
        ("detector_control_b_found_planted_orphan", ctrl.get("detector_control_b_found_planted_orphan")),
        ("hash_fires_on_stale_bytes", ctrl.get("hash_fires_on_stale_bytes")),
        ("planted_negative_control", ctrl.get("planted_negative_control")),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:ARC-0019-probe1 {name}")
            return 1

    live = L.live_report(REPO)
    a = int(live["registry_not_deployed_count"])
    b = int(live["deployed_not_in_registry_count"])
    h = int(live["hash_mismatch_count"])
    d = int(live["disagreement_count"])
    print(
        f"live A={a} B={b} H={h} disagreement={d} "
        f"fails_today={live['fails_today']} install_present={live['install_root_present']}"
    )
    if a < 1:
        print("FAILED:ARC-0019-probe1 live registry-not-deployed unexpectedly zero")
        return 1
    if not live["install_root_present"] and a != int(live["registry_id_count"]):
        print("FAILED:ARC-0019-probe1 live A != registry ids with absent install root")
        return 1
    if d != a + b + h:
        print("FAILED:ARC-0019-probe1 disagreement_count is not A+B+H")
        return 1
    # Detector-control already proved B can see a planted orphan, so live B=0 is allowed.

    if not ART.is_file():
        print("FAILED:ARC-0019-probe1 FAILURE-MODES.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0019-probe1 self-declared {doc.get('state')}")
        return 1
    live_doc = doc.get("live_reconciliation") or {}
    if int(live_doc.get("registry_not_deployed_count")) != a:
        print("FAILED:ARC-0019-probe1 artifact Direction A count drift")
        return 1
    if int(live_doc.get("deployed_not_in_registry_count")) != b:
        print("FAILED:ARC-0019-probe1 artifact Direction B count drift")
        return 1
    if int(live_doc.get("hash_mismatch_count")) != h:
        print("FAILED:ARC-0019-probe1 artifact hash-mismatch count drift")
        return 1
    if int(live_doc.get("disagreement_count")) != d:
        print("FAILED:ARC-0019-probe1 artifact disagreement count drift")
        return 1
    for forbidden in ("combined_agree_count", "combined_consistent_count", "agreement_score"):
        if forbidden in live_doc:
            print(f"FAILED:ARC-0019-probe1 {forbidden} present")
            return 1
    if "SUCCESS:ARC-0019" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0019-probe1 sentinel absent")
        return 1
    print("SUCCESS:ARC-0019-probe1 both-states planted-orphan live counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
