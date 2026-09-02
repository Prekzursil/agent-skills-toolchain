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
POLICY_COUNT_ABSTENTION = "count-abstention"
PROXY_ORIGIN_MARKER = "PROXY-ORIGIN"
ORIGIN_AGENT = KIND_AGENT
ORIGIN_HUMAN = KIND_HUMAN
ORIGIN_PROXY = "proxy"
CHOICES = (APPROVE, REJECT, ABSTAIN)
ABSTENTION_POLICIES = (POLICY_EXCLUDE_ABSTENTION, POLICY_COUNT_ABSTENTION)


def tally_records(
    records: list[dict[str, Any]],
    include_proxy: bool = False,
    abstention_policy_id: str = POLICY_EXCLUDE_ABSTENTION,
) -> dict[str, Any]:
    """Tally ballot records ``{"seat_id", "origin", "choice"}`` into counts.

    ``origin`` is one of ORIGIN_AGENT / ORIGIN_HUMAN / ORIGIN_PROXY; proxy
    ballots are excluded unless ``include_proxy`` is true. Under
    POLICY_EXCLUDE_ABSTENTION abstentions do not count toward ``n``; under
    POLICY_COUNT_ABSTENTION they do. A seat may vote once: a duplicate
    ``seat_id`` raises ValueError, as does an unknown choice or policy.
    The tally is evidence-blind by construction: records carry no evidence
    field and none is consulted.
    """
    if abstention_policy_id not in ABSTENTION_POLICIES:
        raise ValueError(f"unknown abstention policy {abstention_policy_id!r}")
    approve = reject = abstain = 0
    excluded_proxy: list[str] = []
    seen: set[str] = set()
    for rec in records:
        seat_id = str(rec.get("seat_id") or "")
        if not seat_id:
            raise ValueError("ballot record lacks seat_id")
        if seat_id in seen:
            raise ValueError(f"duplicate ballot for seat {seat_id!r}")
        seen.add(seat_id)
        choice = rec.get("choice")
        if choice not in CHOICES:
            raise ValueError(f"unknown choice {choice!r} for seat {seat_id!r}")
        origin = rec.get("origin") or ORIGIN_AGENT
        if origin == ORIGIN_PROXY and not include_proxy:
            excluded_proxy.append(seat_id)
            continue
        if choice == APPROVE:
            approve += 1
        elif choice == REJECT:
            reject += 1
        else:
            abstain += 1
    n = approve + reject
    if abstention_policy_id == POLICY_COUNT_ABSTENTION:
        n += abstain
    return {
        "n": n,
        "approve": approve,
        "reject": reject,
        "abstain": abstain,
        "excluded_proxy": excluded_proxy,
        "include_proxy": bool(include_proxy),
        "abstention_policy_id": abstention_policy_id,
    }


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
