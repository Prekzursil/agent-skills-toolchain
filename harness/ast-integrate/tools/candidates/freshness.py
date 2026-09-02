"""TTL due-list over candidate evidence. Wall clock is banned in this file."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

TTL_SOURCE_POLICY = "policy-table"
TTL_SOURCE_WORST_CASE = "worst-case-default"
DECAYED_STALE = "STALE"
REASON_TTL_EXPIRED = "ttl-expired"
REASON_MISSING_VERIFIED = "missing-verified"
REASON_MISSING_LAST_VERIFIED = "missing-last-verified"
REASON_UNKNOWN_CLASS = "unknown-evidence-class"


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

    def worst_case_ttl(self) -> int:
        """The shortest TTL in the table: what an unclassified or unverified row gets."""
        return int(min(self.classes.values())) if self.classes else 0

    def resolve(self, evidence_class: str) -> tuple[int, str]:
        """(ttl seconds, ttl_source) for a class; unknown classes fall to the worst case."""
        if evidence_class in self.classes:
            return int(self.classes[evidence_class]), TTL_SOURCE_POLICY
        return self.worst_case_ttl(), TTL_SOURCE_WORST_CASE


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
    decayed_verdict: str = DECAYED_STALE
    ttl_source: str = TTL_SOURCE_POLICY
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.reasons:
            self.reasons = (self.reason,)
        elif self.reason not in self.reasons:
            self.reasons = (self.reason, *self.reasons)

    @property
    def citeable(self) -> bool:
        """A due item's verdict has decayed; only a still-GREEN verdict may be cited."""
        return self.decayed_verdict == "GREEN"


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
    """Rows whose stored verdict may no longer be cited at ``clock``.

    A row with no ``last_verified`` is due immediately (fail-closed) and is aged
    against the worst-case TTL; a verified row is due once its age exceeds its
    class TTL.  Every due item decays to STALE regardless of the stored verdict.
    """
    if not isinstance(clock, InjectedClock):
        raise TypeError("clock must be InjectedClock")
    now = clock.now()
    due: list[DueItem] = []
    for row in rows:
        ttl, ttl_source = table.resolve(row.evidence_class)
        class_reasons = (REASON_UNKNOWN_CLASS,) if ttl_source == TTL_SOURCE_WORST_CASE else ()
        if row.last_verified <= 0:
            due.append(
                DueItem(
                    row.candidate_id,
                    REASON_MISSING_VERIFIED,
                    0,
                    ttl,
                    row.stored_verdict,
                    prior_verdict=row.stored_verdict,
                    ttl_source=TTL_SOURCE_WORST_CASE,
                    reasons=(REASON_MISSING_VERIFIED, REASON_MISSING_LAST_VERIFIED, *class_reasons),
                )
            )
            continue
        age = now - int(row.last_verified)
        if age > ttl:
            due.append(
                DueItem(
                    row.candidate_id,
                    REASON_TTL_EXPIRED,
                    age,
                    ttl,
                    row.stored_verdict,
                    prior_verdict=row.stored_verdict,
                    ttl_source=ttl_source,
                    reasons=(REASON_TTL_EXPIRED, *class_reasons),
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
        "prior_verdict": item.prior_verdict,
        "decayed_verdict": item.decayed_verdict,
        "citeable": item.citeable,
        "ttl_source": item.ttl_source,
        "reasons": list(item.reasons),
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


def schedule(
    rows: Iterable[CandidateEvidence],
    clock: InjectedClock,
    table: TtlTable,
    transport: Any = None,
) -> list[dict[str, Any]]:
    """Re-verification schedule at ``clock``: one entry per due candidate.

    Purely cache-driven — the transport is only recorded as the channel a later
    re-verification would use, never called here, so an emit-time scheduler can
    never leak a network call.  Entries are ordered by urgency: missing
    verification first, then the most over-due TTL, then by id.
    """
    if not isinstance(clock, InjectedClock):
        raise TypeError("clock must be InjectedClock")
    rows = list(rows)
    now = clock.now()
    cache_ttl = int(table.classes.get("maintenance-cache", 86400))
    by_id = {row.candidate_id: row for row in rows}
    entries: list[dict[str, Any]] = []
    for item in compute_due_list(rows, clock, table):
        row = by_id[item.candidate_id]
        cached_at = int((row.maintenance or {}).get("cached_at") or row.last_verified or 0)
        maintenance_cache_fresh = (now - cached_at) <= cache_ttl
        archived = bool(row.archived or (row.maintenance or {}).get("archived"))
        entries.append(
            {
                "candidate_id": item.candidate_id,
                "action": "re-verify",
                "priority": 0 if item.reason == REASON_MISSING_VERIFIED else 1,
                "overdue_s": max(0, item.age_s - item.ttl_s),
                "reasons": list(item.reasons),
                "ttl_source": item.ttl_source,
                "decayed_verdict": item.decayed_verdict,
                "citeable": item.citeable,
                "archived_upstream": archived,
                "maintenance_cache_fresh": maintenance_cache_fresh,
                "transport": type(transport).__name__ if transport is not None else None,
                "network_called": False,
            }
        )
    entries.sort(key=lambda e: (e["priority"], -e["overdue_s"], e["candidate_id"]))
    return entries
