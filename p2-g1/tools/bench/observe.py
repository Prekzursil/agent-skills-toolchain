"""Network observer for live-source detection."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NetworkObserver:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def record(self, url: str, **kwargs: Any) -> None:
        self.calls.append({"url": url, **kwargs})

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self.calls)
