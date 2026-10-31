"""Baseline agent source for the deployed cockpit (TST-0152)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BaselineSource:
    agents: list[dict[str, Any]] = field(default_factory=list)

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self.agents)
