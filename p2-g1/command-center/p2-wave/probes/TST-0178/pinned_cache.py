#!/usr/bin/env python3
"""TST-0178 measured layer: LRU cache with a pin table (and a pinning-disabled mutant).

Production note (recorded in the receipt): platform/plugin/cache.py Cache.prune
evicts strictly by mtime LRU and has NO pin/reference-count concept, so the
catalog question (can eviction remove an entry a running unit holds?) is
measured on this module: an LRU + pin set where evict() skips pinned entries,
plus a known-broken mutant that ignores the pin table.
"""
from __future__ import annotations

import threading
import time


class PinnedCache:
    def __init__(self, max_bytes: int, pinning_enabled: bool = True):
        self.max_bytes = max_bytes
        self.pinning_enabled = pinning_enabled
        self.entries: dict[str, tuple[bytes, float]] = {}  # key -> (payload, last_touch)
        self.pins: dict[str, int] = {}  # key -> active reader count
        self.evicted: list[str] = []
        self.lock = threading.Lock()

    def put(self, key: str, payload: bytes) -> None:
        with self.lock:
            self.entries[key] = (payload, time.monotonic())
            self._prune_locked()

    def get(self, key: str) -> bytes | None:
        with self.lock:
            e = self.entries.get(key)
            if e is None:
                return None
            self.entries[key] = (e[0], time.monotonic())  # LRU touch
            return e[0]

    def acquire(self, key: str) -> bytes | None:
        """A running unit takes a read handle: pins the entry for the hold."""
        with self.lock:
            e = self.entries.get(key)
            if e is None:
                return None
            self.pins[key] = self.pins.get(key, 0) + 1
            return e[0]

    def release(self, key: str) -> None:
        with self.lock:
            n = self.pins.get(key, 0) - 1
            if n <= 0:
                self.pins.pop(key, None)
            else:
                self.pins[key] = n

    def _note_violation(self, key: str) -> None:
        """Hook: subclass records evict-of-pinned events here."""

    def _prune_locked(self) -> int:
        total = sum(len(p) for p, _ in self.entries.values())
        if total <= self.max_bytes:
            return 0
        evicted = 0
        for k in sorted(self.entries, key=lambda k: self.entries[k][1]):  # LRU first
            if total <= self.max_bytes:
                break
            if k in self.pins:
                if self.pinning_enabled:
                    continue  # pin table protects the entry
                self._note_violation(k)  # mutant path: pinned entry actually evicted
            payload, _ = self.entries.pop(k)
            total -= len(payload)
            self.evicted.append(k)
            evicted += 1
        return evicted

    def prune(self) -> int:
        with self.lock:
            return self._prune_locked()
