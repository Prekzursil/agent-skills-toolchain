"""Registry health metrics for the cockpit pane."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

METRIC_IDS = ("index_lint_status", "mirror_conflict_count", "blocked_publish_count")


class RegistryHealth:
    def __init__(self, store: Any, *, clock: Any, window: timedelta) -> None:
        self.store = store
        self.clock = clock
        self.window = window
        self._snap: dict[str, Any] | None = None

    def measure_all(self) -> dict[str, Any]:
        payload = getattr(self.store, "payload", {}) or {}
        now = self.clock.now()
        measured_at = payload.get("measured_at") or now.isoformat()
        values = {k: payload.get(k) for k in METRIC_IDS}
        age = now - datetime.fromisoformat(str(measured_at).replace("Z", "+00:00"))
        stale = age > self.window
        statuses = {k: ("STALE" if stale else "FRESH") for k in METRIC_IDS}
        self._snap = {
            "values": values,
            "statuses": statuses,
            "measured_at": {k: measured_at for k in METRIC_IDS},
            "stale": stale,
        }
        return self._snap

    def snapshot(self) -> dict[str, Any]:
        return self._snap or self.measure_all()
