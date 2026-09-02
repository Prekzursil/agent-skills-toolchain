"""Independent provider surface: its own 429 counter and rate-limit headers.

The scheduler's self-reported histogram is evidence A. This module is evidence B.
If the scheduler claims compliance while this surface records 429s, the provider
counter wins and the run is a detector-failure.
"""
from __future__ import annotations

from typing import Any

from scheduler import Clock


class ProviderSurface:
    def __init__(self, name: str, limit_per_minute: int, clock: Clock) -> None:
        if limit_per_minute < 1:
            raise ValueError("limit_per_minute must be >= 1")
        self.name = name
        self.limit_per_minute = int(limit_per_minute)
        self.clock = clock
        self.arrivals: list[float] = []
        self.http_429 = 0
        self.http_200 = 0
        self.http_5xx = 0
        self.headers_log: list[dict[str, Any]] = []
        self._fail_5xx_once = 0

    def plant_one_503(self) -> None:
        self._fail_5xx_once += 1

    def handle(self, _request: dict[str, Any] | None = None) -> dict[str, Any]:
        now = self.clock.now()
        if self._fail_5xx_once > 0:
            self._fail_5xx_once -= 1
            self.http_5xx += 1
            headers = {"Retry-After": "1"}
            rec = {"status": 503, "headers": headers, "at": now}
            self.headers_log.append(rec)
            return {"status": 503, "headers": headers, "body": "unavailable"}
        window = [t for t in self.arrivals if now - t < 60.0]
        remaining = self.limit_per_minute - len(window)
        if remaining <= 0:
            self.http_429 += 1
            oldest = min(window) if window else now
            retry_after = max(1, int(60.0 - (now - oldest)))
            headers = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(self.limit_per_minute),
                "X-RateLimit-Remaining": "0",
            }
            self.headers_log.append({"status": 429, "headers": headers, "at": now})
            return {"status": 429, "headers": headers, "body": "rate limited"}
        self.arrivals.append(now)
        self.http_200 += 1
        headers = {
            "X-RateLimit-Limit": str(self.limit_per_minute),
            "X-RateLimit-Remaining": str(remaining - 1),
        }
        self.headers_log.append({"status": 200, "headers": headers, "at": now})
        return {"status": 200, "headers": headers, "body": "ok"}

    def burst_unscheduled(self, n: int) -> list[dict[str, Any]]:
        """Naive herd: n calls with no scheduler, same clock instant."""
        return [self.handle({}) for _ in range(n)]

    def report(self) -> dict[str, Any]:
        rate_headers = [
            h
            for h in self.headers_log
            if h.get("status") == 429
            and isinstance(h.get("headers"), dict)
            and "X-RateLimit-Limit" in h["headers"]
        ]
        return {
            "provider": self.name,
            "limit_per_minute": self.limit_per_minute,
            "http_200": self.http_200,
            "http_429": self.http_429,
            "http_5xx": self.http_5xx,
            "n_arrivals": len(self.arrivals),
            "rate_limit_header_events": len(rate_headers),
            "sample_429_headers": [h["headers"] for h in rate_headers[:5]],
        }
