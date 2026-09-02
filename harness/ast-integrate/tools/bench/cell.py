"""Benchmark cell record."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Cell:
    cell_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"cell_id": self.cell_id, "payload": dict(self.payload)}
