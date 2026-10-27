"""Planted registry store for IMP-0128."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class RegistryStore:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or {}

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(self.payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "RegistryStore":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))


def plant_clean_store(*, measured_at: datetime) -> RegistryStore:
    ts = measured_at.isoformat()
    return RegistryStore(
        {
            "index_lint_status": "CLEAN",
            "mirror_conflict_count": 2,
            "blocked_publish_count": 1,
            "measured_at": ts,
        }
    )
