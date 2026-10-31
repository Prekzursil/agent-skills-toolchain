#!/usr/bin/env python3
"""TST-0176 measured layer: fetch cache with typed negative entries and TTLs.

The unit question: a transient fetch failure must be negatively cached with a
SHORT ttl, clearly distinguished from a genuine absence, and a retry after the
negative ttl must hit the network again. An empty result reporting OK is the
failure being tested.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


class TransientFetchError(Exception):
    """Network/fetch-level failure: retryable, negatively cached SHORT."""


class NotFoundError(Exception):
    """Genuine absence: negatively cached for its FULL ttl."""


@dataclass
class Entry:
    kind: str  # "positive" | "negative-transient" | "negative-genuine"
    value: Any
    stored_at: float
    ttl: float

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.stored_at) >= self.ttl


@dataclass
class NegativeCache:
    positive_ttl: float = 60.0
    transient_negative_ttl: float = 0.25  # SHORT: a blip must re-probe quickly
    genuine_negative_ttl: float = 5.0     # FULL: a real 404 stays cached
    entries: dict = field(default_factory=dict)
    fetch_calls: int = 0

    def get(self, key: str, fetch: Callable[[], Any]) -> Any:
        e = self.entries.get(key)
        if e is not None and not e.expired:
            return e.value
        self.fetch_calls += 1  # network observed
        try:
            value = fetch()
        except TransientFetchError as exc:
            self.entries[key] = Entry("negative-transient", exc, time.monotonic(), self.transient_negative_ttl)
            raise
        except NotFoundError as exc:
            self.entries[key] = Entry("negative-genuine", exc, time.monotonic(), self.genuine_negative_ttl)
            raise
        self.entries[key] = Entry("positive", value, time.monotonic(), self.positive_ttl)
        return value

    def entry(self, key: str) -> Entry | None:
        return self.entries.get(key)


class BrokenEmptyOkCache:
    """KNOWN-BROKEN (the failure this unit tests): reports OK/None on an empty
    cache with a failed fetch - no entry, no error surfaced. Detector fuel only."""


def broken_get(cache: NegativeCache, key: str, fetch: Callable[[], Any]):
    """The broken semantics: swallow the failure, report an empty OK."""
    try:
        return cache.get(key, fetch)
    except Exception:
        return None  # empty result reported as OK - the seeded defect
