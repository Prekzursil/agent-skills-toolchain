"""In-process CRCP service-level counters for wfmon export."""

from __future__ import annotations

import math
import threading
from datetime import datetime, timezone
from typing import Any, Iterable


DEFAULT_PUBLISH_LATENCY_BUCKETS_MS = (100, 250, 500, 1_000, 2_500, 5_000)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_buckets(values: Iterable[float | int]) -> tuple[float | int, ...]:
    buckets: list[float | int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("latency buckets must be numbers")
        if not math.isfinite(value) or value <= 0:
            raise ValueError("latency buckets must be finite and positive")
        buckets.append(value)
    if not buckets:
        raise ValueError("at least one latency bucket is required")
    if buckets != sorted(set(buckets)):
        raise ValueError("latency buckets must be unique and increasing")
    return tuple(buckets)


def _bucket_name(bound: float | int) -> str:
    return f"le_{bound:g}_ms"


class SloCounters:
    """Thread-safe, process-local counters and publish latency histogram."""

    def __init__(
        self,
        publish_latency_buckets_ms: Iterable[float | int] = DEFAULT_PUBLISH_LATENCY_BUCKETS_MS,
    ):
        self.publish_latency_buckets_ms = _normalize_buckets(publish_latency_buckets_ms)
        self._lock = threading.Lock()
        self._started_at = _utc_now()
        self._poll_total = 0
        self._poll_success = 0
        self._publish_count = 0
        self._publish_latency_sum_ms = 0.0
        self._publish_latency_max_ms = 0.0
        self._publish_buckets = [0] * len(self.publish_latency_buckets_ms)
        self._uncertain_sse_count = 0

    def record_poll(self, success: bool) -> None:
        """Record one completed poll attempt."""
        if not isinstance(success, bool):
            raise TypeError("success must be bool")
        with self._lock:
            self._poll_total += 1
            if success:
                self._poll_success += 1

    def record_publish(self, duration_ms: float | int) -> None:
        """Record one completed publish and its non-negative latency."""
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, (int, float)):
            raise TypeError("duration_ms must be a number")
        if not math.isfinite(duration_ms) or duration_ms < 0:
            raise ValueError("duration_ms must be finite and non-negative")
        value = float(duration_ms)
        with self._lock:
            self._publish_count += 1
            self._publish_latency_sum_ms += value
            self._publish_latency_max_ms = max(self._publish_latency_max_ms, value)
            for index, bound in enumerate(self.publish_latency_buckets_ms):
                if value <= bound:
                    self._publish_buckets[index] += 1

    def record_uncertain_sse(self, count: int = 1) -> None:
        """Increment the number of accepted writes lacking terminal SSE evidence."""
        if isinstance(count, bool) or not isinstance(count, int):
            raise TypeError("count must be an integer")
        if count < 0:
            raise ValueError("count must be non-negative")
        with self._lock:
            self._uncertain_sse_count += count

    def export_metrics(self) -> dict[str, Any]:
        """Return a stable, JSON-serializable wfmon metrics snapshot."""
        with self._lock:
            poll_total = self._poll_total
            poll_success = self._poll_success
            publish_count = self._publish_count
            latency_sum = self._publish_latency_sum_ms
            latency_max = self._publish_latency_max_ms
            buckets = dict(
                zip(
                    (_bucket_name(bound) for bound in self.publish_latency_buckets_ms),
                    self._publish_buckets,
                )
            )
            uncertain_sse_count = self._uncertain_sse_count

        buckets["le_inf"] = publish_count
        return {
            "source": "crcp.slo",
            "collected_at": _utc_now(),
            "started_at": self._started_at,
            "poll": {
                "total": poll_total,
                "success": poll_success,
                "failure": poll_total - poll_success,
                "success_rate": poll_success / poll_total if poll_total else None,
            },
            "publish_latency_ms": {
                "count": publish_count,
                "sum": latency_sum,
                "max": latency_max if publish_count else None,
                "buckets": buckets,
            },
            "uncertain_sse_count": uncertain_sse_count,
        }


_DEFAULT_COUNTERS = SloCounters()


def record_poll(success: bool) -> None:
    _DEFAULT_COUNTERS.record_poll(success)


def record_publish(duration_ms: float | int) -> None:
    _DEFAULT_COUNTERS.record_publish(duration_ms)


def record_uncertain_sse(count: int = 1) -> None:
    _DEFAULT_COUNTERS.record_uncertain_sse(count)


def export_metrics() -> dict[str, Any]:
    """Export the module-level counters for wfmon."""
    return _DEFAULT_COUNTERS.export_metrics()


__all__ = [
    "DEFAULT_PUBLISH_LATENCY_BUCKETS_MS",
    "SloCounters",
    "export_metrics",
    "record_poll",
    "record_publish",
    "record_uncertain_sse",
]
