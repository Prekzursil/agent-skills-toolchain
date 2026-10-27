#!/usr/bin/env python3
"""TST-0090 fencing lease store.

FencingLeaseStore: acquire -> monotonic fencing token (1, 2, ...);
reclaim only when the lease is expired, and the token increments on
every successful reclaim. commit(holder, token, payload) is REJECTED
with the stale token recorded whenever the presented token is not the
current one. A timeout-only mutant (no increment) accepts the zombie
write - the receipt's recorded negative control."""
from __future__ import annotations


class LeaseDenied(Exception):
    pass


class FencingLeaseStore:
    def __init__(self, ttl_s: float = 1.0, clock=None) -> None:
        self.ttl = ttl_s
        self.now = clock or (lambda: 0.0)
        self.token = 0
        self.holder = None
        self.held_at = 0.0
        self.rejected: list[dict] = []
        self.committed: list[dict] = []

    def acquire(self, holder: str) -> int:
        if self.holder is not None and self.now() < self.held_at + self.ttl and self.holder != holder:
            raise LeaseDenied("lease held by " + self.holder)
        self.token += 1
        self.holder = holder
        self.held_at = self.now()
        return self.token

    def renew(self, holder: str, token: int) -> None:
        if self.holder != holder or token != self.token:
            raise LeaseDenied("stale renew")
        self.held_at = self.now()

    def reclaim(self, holder: str) -> int:
        if self.holder is not None and self.now() < self.held_at + self.ttl:
            raise LeaseDenied("lease not expired (held by " + self.holder + ")")
        self.token += 1
        self.holder = holder
        self.held_at = self.now()
        return self.token

    def commit(self, holder: str, token: int, payload: str) -> str:
        if self.holder != holder or token != self.token:
            self.rejected.append({"holder": holder, "stale_token": token, "current_token": self.token,
                                  "reason": "stale-fencing-token"})
            return "REJECTED"
        self.committed.append({"holder": holder, "payload": payload})
        return "COMMITTED"


class TimeoutOnlyMutant:
    """Takeover on expiry alone: token NOT incremented - the hole."""

    def __init__(self, ttl_s: float = 1.0, clock=None) -> None:
        self.ttl = ttl_s
        self.now = clock or (lambda: 0.0)
        self.holder = None
        self.held_at = 0.0
        self.committed: list[dict] = []

    def acquire(self, holder: str) -> None:
        self.holder = holder
        self.held_at = self.now()

    def reclaim(self, holder: str) -> None:
        if self.holder is not None and self.now() < self.held_at + self.ttl:
            raise LeaseDenied("not expired")
        self.holder = holder
        self.held_at = self.now()

    def commit(self, holder: str, payload: str) -> str:
        # timeout alone: no fencing - the last writer wins, the hole.
        self.committed.append({"holder": holder, "payload": payload})
        return "COMMITTED"
