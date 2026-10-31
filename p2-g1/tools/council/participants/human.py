"""Hybrid human and agent participation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ABSTAIN = "ABSTAIN"
APPROVE = "APPROVE"
REJECT = "REJECT"
KIND_AGENT = "agent"
KIND_HUMAN = "human"
POLICY_EXCLUDE_ABSTENTION = "exclude-abstention"
PROXY_ORIGIN_MARKER = "PROXY-ORIGIN"


class HumanOnlyViolation(Exception):
    pass


class WindowError(Exception):
    pass


@dataclass
class DeterministicClock:
    t: int = 0

    def now(self) -> int:
        return self.t

    def advance(self, n: int = 1) -> int:
        self.t += n
        return self.t


@dataclass
class Seat:
    seat_id: str
    kind: str
    name: str | None = None
    vote: str | None = None
    proxy_choice: str | None = None


def classify_kind(raw: str) -> str:
    t = raw.lower()
    if "human" in t:
        return KIND_HUMAN
    return KIND_AGENT


def scan_proxy_markers(text: str) -> list[str]:
    if PROXY_ORIGIN_MARKER in text:
        return [PROXY_ORIGIN_MARKER]
    return []


def strip_proxy_markers(text: str) -> str:
    return text.replace(PROXY_ORIGIN_MARKER, "").strip()


@dataclass
class HybridCouncil:
    seats: list[Seat] = field(default_factory=list)
    policy: str = POLICY_EXCLUDE_ABSTENTION
    window_seconds: float = 100.0
    reminder_offset: float = 60.0
    human_only: bool = False
    abstention_policy_id: str = POLICY_EXCLUDE_ABSTENTION
    motion: str = ""
    clock: DeterministicClock | None = None

    def tally(self) -> dict[str, Any]:
        votes = [s.vote or s.proxy_choice for s in self.seats if (s.vote or s.proxy_choice) != ABSTAIN]
        votes = [v for v in votes if v]
        return {"n": len(votes), "approve": votes.count(APPROVE), "reject": votes.count(REJECT)}
