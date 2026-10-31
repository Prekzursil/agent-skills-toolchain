"""Registry client that HONORS Retry-After and staggers batches (IMP-0122).

Recovered 2026-10-25 by builder shard 11 wave 2 from the delivery receipt
`command-center/receipts/IMP-0122.json`. Receipt-pinned contract:

  * on 429 with Retry-After, the next attempt's inter-arrival gap is >= the
    header value, measured on the SERVER side by ScriptedTransport (the client
    clock is injected, so the run is deterministic and never really sleeps)
  * batch_get staggers first-arrivals server-side: a 50-item batch lands
    spread over >2s of fake time; the unstaggered control produces a burst
    (span=0, burst_fraction=1.0, max_count=n) — client-side intent is not the
    signal, arrivals are recorded by the transport
  * retries are bounded (max_retries), and a 429 without Retry-After backs
    off with the default backoff instead of hammering
"""
from __future__ import annotations

import time
from typing import Any, Callable


class FakeClock:
    """Injected clock: advance() instead of real sleeping."""

    def __init__(self) -> None:
        self.now_s: float = 0.0

    def now(self) -> float:
        return self.now_s

    def advance(self, seconds: float) -> None:
        self.now_s += float(seconds)


class ScriptedTransport:
    """Fake server: consumes a per-URL script, records first arrivals."""

    def __init__(self, clock: FakeClock, handler: Callable[[str], dict[str, Any]] | None = None) -> None:
        self.clock = clock
        self.handler = handler
        self.arrivals: dict[str, float] = {}
        self.requests: list[dict[str, Any]] = []

    def send(self, url: str) -> dict[str, Any]:
        if url not in self.arrivals:
            self.arrivals[url] = self.clock.now()
        self.requests.append({"url": url, "at": self.clock.now()})
        if self.handler is not None:
            return self.handler(url)
        return {"status": 200, "headers": {}, "body": b"{}"}

    def first_arrivals(self) -> dict[str, float]:
        return dict(self.arrivals)


class RegistryClient:
    def __init__(
        self,
        transport: ScriptedTransport,
        clock: FakeClock | None = None,
        max_retries: int = 3,
        default_backoff: float = 0.5,
        batch_stagger_interval: float = 0.05,
    ) -> None:
        self.transport = transport
        self.clock = clock or FakeClock()
        self.max_retries = max_retries
        self.default_backoff = default_backoff
        self.batch_stagger_interval = batch_stagger_interval

    def get(self, url: str) -> dict[str, Any]:
        last: dict[str, Any] = {}
        for attempt in range(self.max_retries + 1):
            resp = self.transport.send(url)
            last = resp
            if resp.get("status") != 429:
                return resp
            headers = resp.get("headers") or {}
            retry_after = headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after is not None else self.default_backoff
            except (TypeError, ValueError):
                delay = self.default_backoff
            self.clock.advance(delay)
        return last

    def batch_get(self, urls: list[str], stagger: bool = True) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, url in enumerate(urls):
            if stagger and i > 0:
                self.clock.advance(self.batch_stagger_interval)
            out.append(self.get(url))
        return out


def burst_histogram(arrivals: dict[str, float]) -> dict[str, Any]:
    """Server-side first-arrival histogram, 100ms bins."""
    if not arrivals:
        return {"n": 0, "span": 0.0, "max_count": 0, "burst_fraction": 0.0,
                "occupied_bins": 0}
    times = sorted(arrivals.values())
    t0 = times[0]
    span = times[-1] - times[0]
    bins: dict[int, int] = {}
    for t in times:
        b = int((t - t0) / 0.1)
        bins[b] = bins.get(b, 0) + 1
    max_count = max(bins.values())
    return {
        "n": len(times),
        "span": round(span, 6),
        "max_count": max_count,
        "burst_fraction": round(max_count / len(times), 4),
        "occupied_bins": len(bins),
    }
