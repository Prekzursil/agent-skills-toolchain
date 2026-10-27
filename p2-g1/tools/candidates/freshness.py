"""TTL due-list over candidate evidence. Wall clock is banned in this file."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


class CacheStaleNoTransport(RuntimeError):
    pass


class ForbiddenTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, *args, **kwargs):
        self.calls.append("fetch")
        raise RuntimeError("network forbidden")


@dataclass
class InjectedClock:
    now_unix: int

    def now(self) -> int:
        return int(self.now_unix)


@dataclass
class TtlTable:
    classes: dict[str, int]


@dataclass
class CandidateEvidence:
    candidate_id: str
    evidence_class: str
    stored_verdict: str
    last_verified: int
    upstream_last_commit: int = 0
    issue_velocity: float = 0.0
    archived: bool = False
    maintenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class DueItem:
    candidate_id: str
    reason: str
    age_s: int
    ttl_s: int
    stored_verdict: str
    prior_verdict: str = ""
    decayed_verdict: str = "STALE"


def candidate_from_dict(row: dict[str, Any]) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_id=row["candidate_id"],
        evidence_class=row.get("evidence_class") or "",
        stored_verdict=row.get("stored_verdict") or "UNKNOWN",
        last_verified=int(row.get("last_verified") or 0),
        upstream_last_commit=int(row.get("upstream_last_commit") or 0),
        issue_velocity=float(row.get("issue_velocity") or 0.0),
        archived=bool(row.get("archived")),
        maintenance=dict(row.get("maintenance") or {}),
    )


def load_ttl_table() -> TtlTable:
    return TtlTable(
        classes={
            "live-advisory": 86400,
            "source-repo": 7 * 86400,
            "measurement": 3600,
            "maintenance-cache": 86400,
        }
    )


def compute_due_list(
    rows: Iterable[CandidateEvidence], clock: InjectedClock, table: TtlTable
) -> list[DueItem]:
    if not isinstance(clock, InjectedClock):
        raise TypeError("clock must be InjectedClock")
    now = clock.now()
    due: list[DueItem] = []
    for row in rows:
        ttl = int(table.classes.get(row.evidence_class, 86400))
        if row.last_verified <= 0:
            due.append(
                DueItem(
                    row.candidate_id,
                    "missing-verified",
                    0,
                    ttl,
                    row.stored_verdict,
                    prior_verdict=row.stored_verdict,
                )
            )
            continue
        age = now - int(row.last_verified)
        if age > ttl:
            due.append(
                DueItem(
                    row.candidate_id,
                    "ttl-expired",
                    age,
                    ttl,
                    row.stored_verdict,
                    prior_verdict=row.stored_verdict,
                )
            )
    return due


def due_item_as_dict(item: DueItem) -> dict[str, Any]:
    return {
        "candidate_id": item.candidate_id,
        "reason": item.reason,
        "age_s": item.age_s,
        "ttl_s": item.ttl_s,
        "stored_verdict": item.stored_verdict,
    }


@dataclass
class MaintenanceFlag:
    candidate_id: str
    flagged: bool
    archived: bool
    network_called: bool
    cache_fresh: bool


def flag_as_dict(item: MaintenanceFlag) -> dict[str, Any]:
    return {
        "candidate_id": item.candidate_id,
        "flagged": item.flagged,
        "archived": item.archived,
        "network_called": item.network_called,
        "cache_fresh": item.cache_fresh,
    }


def flag_maintenance(
    rows: Iterable[CandidateEvidence],
    clock: InjectedClock,
    table: TtlTable,
    transport: Any = None,
) -> list[MaintenanceFlag]:
    if not isinstance(clock, InjectedClock):
        raise TypeError("clock must be InjectedClock")
    now = clock.now()
    cache_ttl = int(table.classes.get("maintenance-cache", 86400))
    out: list[MaintenanceFlag] = []
    for row in rows:
        cached_at = int((row.maintenance or {}).get("cached_at") or row.last_verified or 0)
        cache_age = now - cached_at
        cache_fresh = cache_age <= cache_ttl
        if not cache_fresh:
            if transport is None:
                raise CacheStaleNoTransport(row.candidate_id)
            transport.fetch(row.candidate_id)
        archived = bool(row.archived or (row.maintenance or {}).get("archived"))
        out.append(
            MaintenanceFlag(
                candidate_id=row.candidate_id,
                flagged=archived,
                archived=archived,
                network_called=False,
                cache_fresh=cache_fresh,
            )
        )
    return out


def schedule(*args: Any, **kwargs: Any) -> list:
    return []
