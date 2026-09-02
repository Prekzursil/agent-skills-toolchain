"""Shared fixture store for IMP-0128 named probes."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MARKET = REPO / "tools" / "marketplace"
MON = REPO / "tools" / "monitorcore"
for p in (str(MARKET), str(MON)):
    if p not in sys.path:
        sys.path.insert(0, p)

from freshness import Clock  # noqa: E402
from registry_health import RegistryHealth  # noqa: E402
from registry_store import plant_clean_store  # noqa: E402

T0 = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)
WINDOW = timedelta(hours=24)


def make_health(stale: bool = False) -> tuple[RegistryHealth, Clock, Path]:
    clock = Clock(T0)
    store = plant_clean_store(measured_at=T0)
    health = RegistryHealth(store, clock=clock, window=WINDOW)
    health.measure_all()
    if stale:
        clock.advance(timedelta(hours=25))
    fixture = HERE / "fixtures"
    fixture.mkdir(parents=True, exist_ok=True)
    path = fixture / ("stale-store.json" if stale else "live-store.json")
    store.save(path)
    return health, clock, path
