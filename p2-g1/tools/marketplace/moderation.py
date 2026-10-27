"""Moderation queue: report → dispute window → dispute → resolve."""
from __future__ import annotations

from typing import Any

from .event_log import EventLog, ImmutableRecordError

REPORT_BODY_FIXTURE = "REPORT-BODY-FIXTURE-IMP-0110"
DISPUTE_BODY_FIXTURE = "DISPUTE-BODY-FIXTURE-IMP-0110"
FULL_CYCLE_EVENT_TYPES = [
    "report-filed",
    "dispute-window-opened",
    "dispute-filed",
    "report-resolved",
]
MUTATION_REFUSED = "mutation-refused"
RESOLVE_REFUSED = "resolve-refused"


class DisputeOpportunityRequired(Exception):
    def __init__(self, refusal: dict[str, Any]) -> None:
        super().__init__("dispute-opportunity-required")
        self.refusal = refusal


class ModerationQueue:
    def __init__(self, log: EventLog | None = None) -> None:
        self.log = log if log is not None else EventLog()
        self._reports: dict[str, dict[str, Any]] = {}
        self._n = 0

    def file_report(
        self,
        package_id: str,
        category: str,
        reporter_id: str,
        body: str,
    ) -> dict[str, Any]:
        self._n += 1
        rid = f"rep-{self._n:04d}"
        rec = {
            "report_id": rid,
            "package_id": package_id,
            "category": category,
            "reporter_id": reporter_id,
            "body": body,
            "state": "filed",
            "dispute": None,
            "resolution": None,
            "window_open": False,
        }
        self._reports[rid] = rec
        self.log.append(
            "report-filed",
            {"report_id": rid, "body": body, "package_id": package_id},
            actor_id=reporter_id,
        )
        return {"report_id": rid, **rec}

    def open_dispute_window(self, report_id: str, *, actor_id: str = "moderator") -> None:
        rec = self._reports[report_id]
        rec["window_open"] = True
        rec["state"] = "window-open"
        self.log.append(
            "dispute-window-opened",
            {"report_id": report_id},
            actor_id=actor_id,
        )

    def file_dispute(self, report_id: str, *, publisher_id: str, body: str) -> dict[str, Any]:
        rec = self._reports[report_id]
        rec["dispute"] = {"body": body, "publisher_id": publisher_id}
        rec["state"] = "disputed"
        self.log.append(
            "dispute-filed",
            {"report_id": report_id, "body": body},
            actor_id=publisher_id,
        )
        return rec["dispute"]

    def resolve(
        self,
        report_id: str,
        outcome: str,
        actor_id: str,
        rationale: str,
    ) -> dict[str, Any]:
        rec = self._reports[report_id]
        if rec.get("dispute") is None:
            refusal = self.log.append(
                RESOLVE_REFUSED,
                {"report_id": report_id, "event_type": RESOLVE_REFUSED},
                actor_id=actor_id,
            )
            refusal["event_type"] = RESOLVE_REFUSED
            raise DisputeOpportunityRequired(refusal)
        rec["resolution"] = {"outcome": outcome, "rationale": rationale}
        rec["state"] = "resolved"
        self.log.append(
            "report-resolved",
            {"report_id": report_id, "outcome": outcome},
            actor_id=actor_id,
        )
        return rec

    def try_edit_report(self, report_id: str, new_body: str, *, actor_id: str) -> None:
        self.log.append(
            MUTATION_REFUSED,
            {"op": "edit_report", "report_id": report_id, "attempt": new_body},
            actor_id=actor_id,
        )
        raise ImmutableRecordError("edit-report")

    def try_delete_report(self, report_id: str, *, actor_id: str) -> None:
        self.log.append(
            MUTATION_REFUSED,
            {"op": "delete_report", "report_id": report_id},
            actor_id=actor_id,
        )
        raise ImmutableRecordError("delete-report")

    def try_edit_dispute(self, report_id: str, new_body: str, *, actor_id: str) -> None:
        self.log.append(
            MUTATION_REFUSED,
            {"op": "edit_dispute", "report_id": report_id, "attempt": new_body},
            actor_id=actor_id,
        )
        raise ImmutableRecordError("edit-dispute")

    def cycle_event_types(self, report_id: str) -> list[str]:
        types = []
        for ev in self.log.events():
            payload = ev.get("payload") or {}
            if payload.get("report_id") == report_id or ev.get("event_type") in FULL_CYCLE_EVENT_TYPES:
                if payload.get("report_id") in {None, report_id}:
                    types.append(ev["event_type"])
        return [t for t in types if t in FULL_CYCLE_EVENT_TYPES]

    def audit(self, report_id: str) -> dict[str, Any]:
        rec = self._reports[report_id]
        return {
            "report": {"body": rec["body"]},
            "dispute": rec.get("dispute") or {},
            "state": rec["state"],
            "resolution": rec.get("resolution"),
        }


def run_full_cycle(queue: ModerationQueue | None = None) -> dict[str, Any]:
    q = queue if queue is not None else ModerationQueue()
    filed = q.file_report(
        package_id="acme.widget",
        category="spam",
        reporter_id="user:reporter-1",
        body=REPORT_BODY_FIXTURE,
    )
    rid = filed["report_id"]
    q.open_dispute_window(rid)
    q.file_dispute(rid, publisher_id="publisher:acme", body=DISPUTE_BODY_FIXTURE)
    resolved = q.resolve(
        rid,
        outcome="upheld",
        actor_id="moderator:queue",
        rationale="publisher responded",
    )
    return {
        "report_id": rid,
        "report": {"body": resolved["body"]},
        "dispute": resolved["dispute"],
        "resolution": resolved["resolution"],
        "state": resolved["state"],
        "events": q.log.events(),
    }


# --- ADV-0068 deny-by-default install gate (coexists with IMP-0110 queue) ---

from dataclasses import dataclass, field

GATING_STATES = frozenset({"open", "disputed", "confirmed"})
AUTHORIZED_SIGNERS = frozenset({"moderator", "maintainer", "security-researcher"})
LEGIT = "fixture.legit-hello"
EVIL = "fixture.malware-beacon"


@dataclass
class PackageState:
    package_id: str
    yanked: bool = False
    warning_banner: bool = False
    install_blocked: bool = False


@dataclass
class ReportRecord:
    report_id: str
    reporter_id: str
    package_id: str
    reason: str
    status: str = "queued"
    automatic_enforcement: bool = False
    documented_outcome: str = "report-accepted-pending-human-review"


@dataclass
class Advisory:
    advisory_id: str
    package_id: str
    signer_id: str
    signer_role: str
    summary: str
    state: str = "open"


@dataclass
class Dispute:
    dispute_id: str
    advisory_id: str
    filer_id: str
    state: str = "open"


@dataclass
class InstallResult:
    allowed: bool
    package_id: str
    reason: str
    gating_advisory_ids: list[str] = field(default_factory=list)
    override_recorded: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "gating_advisory_ids": list(self.gating_advisory_ids),
            "override_recorded": self.override_recorded,
            "package_id": self.package_id,
            "reason": self.reason,
        }


class ModerationEngine:
    def __init__(self) -> None:
        self.packages: dict[str, PackageState] = {
            LEGIT: PackageState(LEGIT),
            EVIL: PackageState(EVIL),
        }
        self._reports: list[ReportRecord] = []
        self._advisories: list[Advisory] = []
        self._disputes: list[Dispute] = []
        self._n_report = 0
        self._n_adv = 0
        self._n_dis = 0

    def reports_for(self, package_id: str) -> list[ReportRecord]:
        return [r for r in self._reports if r.package_id == package_id]

    def file_report(self, reporter_id: str, package_id: str, reason: str) -> ReportRecord:
        self._n_report += 1
        rec = ReportRecord(
            report_id=f"report-{self._n_report:04d}",
            reporter_id=reporter_id,
            package_id=package_id,
            reason=reason,
        )
        self._reports.append(rec)
        return rec

    def file_advisory(
        self, signer_id: str, signer_role: str, package_id: str, summary: str
    ) -> dict[str, Any]:
        if signer_role not in AUTHORIZED_SIGNERS:
            return {
                "accepted": False,
                "reason": "unauthorized-signer",
                "healthy_still_installable": True,
            }
        self._n_adv += 1
        adv = Advisory(
            advisory_id=f"advisory-{self._n_adv:04d}",
            package_id=package_id,
            signer_id=signer_id,
            signer_role=signer_role,
            summary=summary,
            state="open",
        )
        self._advisories.append(adv)
        pkg = self.packages.setdefault(package_id, PackageState(package_id))
        pkg.install_blocked = True
        return {"accepted": True, "advisory": adv, "reason": "authorized"}

    def file_dispute(self, filer_id: str, advisory_id: str) -> Dispute:
        self._n_dis += 1
        rec = Dispute(
            dispute_id=f"dispute-{self._n_dis:04d}",
            advisory_id=advisory_id,
            filer_id=filer_id,
            state="open",
        )
        self._disputes.append(rec)
        for adv in self._advisories:
            if adv.advisory_id == advisory_id:
                adv.state = "disputed"
        return rec

    def open_advisories(self, package_id: str) -> list[Advisory]:
        return [
            a
            for a in self._advisories
            if a.package_id == package_id and a.state in GATING_STATES
        ]

    def auto_state(self, package_id: str) -> dict[str, Any]:
        pkg = self.packages.setdefault(package_id, PackageState(package_id))
        blocked = bool(self.open_advisories(package_id)) or pkg.install_blocked
        return {
            "yanked": pkg.yanked,
            "warning_banner": pkg.warning_banner,
            "install_blocked": blocked,
        }

    def install(self, package_id: str) -> InstallResult:
        open_ids = [a.advisory_id for a in self.open_advisories(package_id)]
        if open_ids:
            return InstallResult(
                allowed=False,
                package_id=package_id,
                reason="open-advisory",
                gating_advisory_ids=open_ids,
            )
        pkg = self.packages.setdefault(package_id, PackageState(package_id))
        if pkg.yanked or pkg.install_blocked:
            return InstallResult(
                allowed=False, package_id=package_id, reason="blocked", gating_advisory_ids=open_ids
            )
        return InstallResult(allowed=True, package_id=package_id, reason="clean")


def fixture_engine() -> ModerationEngine:
    return ModerationEngine()


def report_identities(n: int) -> list[str]:
    return [f"reporter-{i:04d}" for i in range(1, n + 1)]


def disputed_remains_gating() -> bool:
    return "disputed" in GATING_STATES


def install_calls_open_advisories() -> bool:
    import inspect

    return "open_advisories" in inspect.getsource(ModerationEngine.install)


def mutant_auto_delist(engine: ModerationEngine, package_id: str, threshold: int = 5) -> bool:
    n = len(engine.reports_for(package_id))
    if n >= threshold:
        engine.packages[package_id].yanked = True
        engine.packages[package_id].install_blocked = True
        return True
    return False
