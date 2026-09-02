#!/usr/bin/env python3
"""Probe 1: healthy-fixture aggregate (evidence signal 1) plus the contracted tests.

Catalog evidence (1): the aggregate report on a healthy machine — here a
planted known-good observation root, not a claim about this incomplete
worktree. Also re-runs test_health_framework.py including
test_blocked_probe_prevents_healthy_aggregate.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import health_check as hc  # noqa: E402
import health_probes as hp  # noqa: E402

TEST = PLUGIN / "tests" / "test_health_framework.py"


def main() -> int:
    env = {**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, "-B", str(TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=90,
    )
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()
    print(tail)
    if proc.returncode != 0:
        print("FAILED:IMP-0043-probe1 unit tests")
        return 1
    if "SUCCESS:IMP-0043-tests" not in tail:
        print("FAILED:IMP-0043-probe1 tests sentinel absent")
        return 1
    if "test_blocked_probe_prevents_healthy_aggregate" not in tail:
        print("FAILED:IMP-0043-probe1 catalog test name did not run")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0043-p1-") as td:
        root = Path(td)
        hp.plant_healthy_tree(root)
        report = hc.run_all(hc.default_registry(), hc.HealthContext(root=root))
    print(json.dumps(report.to_dict(), sort_keys=True, indent=2))
    if not report.healthy:
        print(f"FAILED:IMP-0043-probe1 expected HEALTHY got {report.reason}")
        return 1
    if report.aggregate != "HEALTHY":
        print(f"FAILED:IMP-0043-probe1 aggregate={report.aggregate}")
        return 1
    ids = [row.probe_id for row in report.probes]
    if ids != list(hp.REQUIRED_PROBE_IDS):
        print(f"FAILED:IMP-0043-probe1 probe set {ids}")
        return 1
    if any(row.state != "SUCCESS" for row in report.probes):
        print("FAILED:IMP-0043-probe1 non-SUCCESS on healthy fixture")
        return 1
    print(
        f"healthy={report.healthy} probes={len(report.probes)} "
        f"blocked={report.blocked_ids} unrun={report.missing_unrun}"
    )
    print("SUCCESS:IMP-0043-probe1 healthy aggregate and catalog tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
