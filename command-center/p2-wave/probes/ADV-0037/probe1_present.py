#!/usr/bin/env python3
"""ADV-0037 Probe 1 (present): plant the synthetic credential and drive every
enumerated REAL credential-diagnosis path on this checkout; sweep stdout,
stderr and every persisted file for the exact body.

Exit code 0 == the campaign executed every target and the detector control
fired/silent as required. Zero leaks is a FINDING, not a precondition.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import probe_common as C  # noqa: E402
import probe_targets_real as R  # noqa: E402


def main() -> int:
    report = R.campaign("happy")
    det = report["detector"]
    executed = sum(1 for t in report["targets"] if t["executed"])
    leaking = [t["id"] for t in report["targets"] if t["hit"]]
    print(json.dumps(report, indent=1, sort_keys=True, default=str))
    print("=== ADV-0037 probe1_present summary ===")
    print(f"targets={len(report['targets'])} executed={executed} leaking={leaking}")
    print(f"detector fired_on_bad={det['fired_on_bad_state']} silent_on_good={det['silent_on_good_state']}")
    ok = executed == len(R.TARGET_IDS) and det["fired_on_bad_state"] and det["silent_on_good_state"]
    print("PROBE1_STATUS=" + ("OK" if ok else "DEGRADED"))
    print("planted_meta=" + json.dumps(C.planted_meta()))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
