#!/usr/bin/env python3
"""Per-provider token bucket for credentialed acquisition calls.

WFA-0034 routes GitHub-metadata reads through this scheduler so the
extractor cannot bypass the arrival stagger (WFA-0029 contract).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class AcquisitionScheduler:
    tokens_per_minute: float = 1000.0
    _buckets: dict[str, float] = field(default_factory=dict)
    _last: dict[str, float] = field(default_factory=dict)
    log: list[dict] = field(default_factory=list)

    def acquire(self, provider: str, target: str) -> None:
        now = time.monotonic()
        last = self._last.get(provider, now)
        tokens = self._buckets.get(provider, self.tokens_per_minute)
        elapsed = max(0.0, now - last)
        tokens = min(self.tokens_per_minute, tokens + elapsed * (self.tokens_per_minute / 60.0))
        if tokens < 1.0 and self.tokens_per_minute < 60.0:
            need = (1.0 - tokens) * (60.0 / max(self.tokens_per_minute, 1e-9))
            time.sleep(min(need, 0.05))
            now = time.monotonic()
            tokens = min(
                self.tokens_per_minute,
                tokens + max(0.0, now - last) * (self.tokens_per_minute / 60.0),
            )
        self._buckets[provider] = max(0.0, tokens - 1.0)
        self._last[provider] = now
        self.log.append({"provider": provider, "target": target})

    def through(self, provider: str, target: str, fn, *args, **kwargs):
        self.acquire(provider, target)
        return fn(*args, **kwargs)
