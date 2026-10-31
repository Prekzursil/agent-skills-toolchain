#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import health_check as hc  # noqa: E402
import health_probes as hp  # noqa: E402


def test_healthy_aggregate() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        hp.plant_healthy_tree(root)
        report = hc.run_all(hc.default_registry(), hc.HealthContext(root=root))
        assert report.healthy and report.aggregate == "HEALTHY"


def test_blocked_probe_prevents_healthy_aggregate() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        hp.plant_healthy_tree(root)
        report = hc.run_all(
            hc.default_registry(),
            hc.HealthContext(root=root, force_state={"hooks_loaded": "BLOCKED"}),
        )
        assert not report.healthy
        assert "hooks_loaded" in report.blocked_ids


def main() -> int:
    test_healthy_aggregate()
    test_blocked_probe_prevents_healthy_aggregate()
    print("test_blocked_probe_prevents_healthy_aggregate")
    print("SUCCESS:IMP-0043-tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
