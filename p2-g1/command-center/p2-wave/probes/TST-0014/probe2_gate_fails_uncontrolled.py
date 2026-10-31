#!/usr/bin/env python3
"""probe2 for TST-0014: the gate FIRES on an uncontrolled detector.

Negative control against the live gate CLI: planting a detector with no
registry row must flip the gate to exit 1 naming it; deleting the plant
restores exit 0. Also proves --census-only never exits non-zero on content.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0014"
GATE = REPO / "tools" / "detector_control" / "gate.py"
UNCONTROLLED = REPO / "tools" / "detector_control" / "fixtures" / "planted" / "uncontrolled-extra.py"


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", "-B", str(GATE), *args],
                          capture_output=True, text=True, cwd=str(REPO))


def main() -> int:
    checks = {}
    baseline = run(["--census-only"])
    checks["census_only_exit_0"] = baseline.returncode == 0
    base = json.loads(baseline.stdout)
    checks["baseline_live_controlled"] = base["uncontrolled_count"] == 0

    UNCONTROLLED.write_text(
        "DETECTOR-ID: UNCONTROLLED-PROBE\nKIND: hook_check\n", encoding="utf-8", newline="\n"
    )
    try:
        failing = run([])
        checks["gate_exit_1_on_uncontrolled"] = failing.returncode == 1
        checks["reason_named"] = "uncontrolled-detectors" in failing.stdout
        checks["uncontrolled_id_named"] = "UNCONTROLLED-PROBE" in failing.stdout
        census_during = run(["--census-only"])
        checks["census_only_still_0_during_failure"] = census_during.returncode == 0
    finally:
        UNCONTROLLED.unlink(missing_ok=True)
    restored = run([])
    checks["gate_exit_0_after_removal"] = restored.returncode == 0
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({"unit_id": UID, "probe": "probe2-gate-fails-uncontrolled", "pass": ok, "checks": checks}))
    if ok:
        print(f"SUCCESS:{UID}-probe2 live gate: census-only 0; planted uncontrolled -> exit 1 reason=uncontrolled-detectors naming UNCONTROLLED-PROBE; removal restores 0")
        return 0
    print(f"FAILED:{UID}-probe2 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
