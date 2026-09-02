"""Controlled IMP-0066 scenario: injected pressure + one live shared service."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
TESTS = PLUGIN / "tests"
for p in (PLUGIN, TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pressure_guard as pg  # noqa: E402
from harness import start_shared_service  # noqa: E402

THRESHOLDS = pg.Thresholds(warn=0.50, shed=0.70, refuse=0.85)


def make_guard(ratio: float) -> tuple[pg.InjectedMeter, pg.PressureGuard]:
    meter = pg.InjectedMeter(committed_units=0, limit_units=1000)
    meter.set_ratio(ratio)
    guard = pg.PressureGuard(
        meter,
        thresholds=THRESHOLDS,
        sink=pg.BoundedWarningSink(cap=32),
        queue=pg.WorkQueue(),
    )
    return meter, guard
