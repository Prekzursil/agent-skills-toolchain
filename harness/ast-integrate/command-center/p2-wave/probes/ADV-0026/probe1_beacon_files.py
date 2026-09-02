#!/usr/bin/env python3
"""Probe 1 — clone fixture, start runtime, observe beacon files.

Mechanically file-system observation. Does not inspect /proc.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harness import run_campaign, verdicts_from  # noqa: E402


def main() -> int:
    doc = run_campaign("beacons")
    targets, tests, overall = verdicts_from(doc)
    clone_clean = not doc.get("any_beacon_after_clone")
    control_clean = not doc.get("any_beacon_control")
    liveness = bool((doc.get("detector_liveness") or {}).get("pass"))
    ok = clone_clean and control_clean and liveness
    out = {
        "pass": ok,
        "probe": "probe1-beacon-files",
        "unit_id": "ADV-0026",
        "overall": overall,
        "clone_wrote_beacons": doc.get("any_beacon_after_clone"),
        "hostile_beacons": doc.get("beacons_after_hostile_run"),
        "control_beacons": doc.get("beacons_after_control_run"),
        "targets": targets,
        "tests": tests,
        "runtime_started": bool((doc.get("hostile_run") or {}).get("started")),
        "runtime_reason": (doc.get("hostile_run") or {}).get("reason"),
        "trust_gate": bool((doc.get("hostile_run") or {}).get("trust_gate")),
        "runtime_stderr_tail": (doc.get("hostile_run") or {}).get("stderr") or "",
        "agents_token_in_stdout": doc.get("agents_token_in_stdout"),
        "detector_liveness": doc.get("detector_liveness"),
    }
    print(json.dumps(out, sort_keys=True))
    if not ok:
        print("FAILED:ADV-0026-probe1 control or detector liveness")
        return 1
    print("SUCCESS:ADV-0026-probe1 clone+runtime beacon-file observation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
