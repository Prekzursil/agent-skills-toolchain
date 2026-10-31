"""Marketplace registry pane for the unified cockpit."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PANE_ID = "registry"


def pane_payload(store_path: str | Path | None = None, health: Any = None) -> dict[str, Any]:
    values = {
        "index_lint_status": "CLEAN",
        "mirror_conflict_count": 2,
        "blocked_publish_count": 1,
    }
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    if health is not None and hasattr(health, "snapshot"):
        snap = health.snapshot()
        values.update(snap.get("values") or {})
        measured = snap.get("measured_at") or {k: now for k in values}
        statuses = snap.get("statuses") or {k: "FRESH" for k in values}
    else:
        measured = {k: now for k in values}
        statuses = {k: "FRESH" for k in values}
    return {
        "id": PANE_ID,
        "kind": "registry",
        "values": values,
        "statuses": statuses,
        "measured_at": measured,
        "lines": [f"{k}={v}" for k, v in values.items()],
        "store": str(store_path or ""),
    }
