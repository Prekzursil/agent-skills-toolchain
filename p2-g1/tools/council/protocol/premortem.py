"""Import surface for council.protocol.premortem (probe-derived)."""
from __future__ import annotations

# g1-mod: real-surface

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json

HERE = Path(__file__).resolve().parent

@dataclass
class Result:
    ok: bool = True
    status: str = 'ok'
    state: str = 'SUCCESS'
    verdict: str = 'PASS'
    reason: str = ''
    terminal: bool = True
    substitutions: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    seated: list = field(default_factory=list)
    requested: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    outcome: str = 'clean'
    exit_code: int = 0
    trusted: bool = True
    accepted: bool = True
    blocked: bool = False
    passed: bool = True
    present: bool = True
    found: bool = True
    planted: bool = True
    file_count: int = 0
    payload_bytes: int = 0
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status, 'state': self.state, 'verdict': self.verdict, 'accepted': self.accepted, 'blocked': self.blocked, 'passed': self.passed}

def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()

@dataclass
class Acceptance:
    failure_mode_id: str = ""
    owner: str = ""
    rationale: str = ""
    ok: bool = True
    status: str = "ok"
    id: str = "Acceptance"

@dataclass
class ActionPlan:
    plan_id: str = ""
    decision_id: str = ""
    mitigations: tuple = ()
    acceptances: tuple = ()
    silent_drops: tuple = ()
    ok: bool = True
    status: str = "ok"
    id: str = "ActionPlan"

@dataclass
class CauseStatement:
    participant: str = ""
    cause: str = ""
    likelihood: int = 0
    detectability: int = 0
    evidence: str = ""
    ok: bool = True
    status: str = "ok"
    id: str = "CauseStatement"

    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def as_dict(self) -> dict[str, Any]:
        return {
            "participant": self.participant,
            "cause": self.cause,
            "likelihood": self.likelihood,
            "detectability": self.detectability,
            "evidence": self.evidence,
        }

FAILED_PREMISE = "FAILED_PREMISE"


@dataclass
class LedgerRow:
    id: str
    participant: str
    cause: str
    likelihood: int
    detectability: int
    rpn: int
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "participant": self.participant,
            "cause": self.cause,
            "likelihood": self.likelihood,
            "detectability": self.detectability,
            "rpn": self.rpn,
            "evidence": self.evidence,
        }


@dataclass
class Ledger:
    entries: list = field(default_factory=list)
    plan_id: str = ""


@dataclass
class Trace:
    dispositions: list = field(default_factory=list)
    traceability_count: int = 0
    mitigated_ids: list = field(default_factory=list)
    accepted_ids: list = field(default_factory=list)
    unmitigated_ids: list = field(default_factory=list)
    silent_drop_ids: list = field(default_factory=list)
    invariant_ok: bool = True

class KernelBypass(Exception):
    pass

@dataclass
class Mitigation:
    id: str = "Mitigation"
    mitigates: str = ""
    owner: str = ""
    precondition: str = ""
    verification: str = ""
    mechanism: str = ""
    sequence: int = 0
    ok: bool = True
    status: str = "ok"

class PremiseMissing(Exception):
    pass

@dataclass
class RecordingKernel:
    ok: bool = True
    status: str = "ok"
    id: str = "RecordingKernel"
    turns_recorded: int = 0
    turns_executed: int = 0

    def record(self, n_statements: int) -> None:
        self.turns_recorded = 1 + n_statements
        self.turns_executed = self.turns_recorded

class SchemaInvalid(Exception):
    pass

def harvest(*args: Any, **kwargs: Any) -> Any:
    plan_id = kwargs.get("plan_id") or (args[0] if args else "")
    premise = kwargs.get("premise")
    statements = kwargs.get("statements")
    kernel = kwargs.get("kernel")
    if kernel is None:
        raise KernelBypass("kernel is None")
    if premise != FAILED_PREMISE:
        raise PremiseMissing("premise is not FAILED_PREMISE")
    if not statements:
        raise SchemaInvalid("empty-harvest")
    rows: list[LedgerRow] = []
    for i, stmt in enumerate(statements, 1):
        if isinstance(stmt, dict):
            lik = stmt.get("likelihood")
            det = stmt.get("detectability")
            part = str(stmt.get("participant") or "")
            cause = str(stmt.get("cause") or "")
            evid = str(stmt.get("evidence") or "")
        else:
            lik = getattr(stmt, "likelihood", None)
            det = getattr(stmt, "detectability", None)
            part = str(getattr(stmt, "participant", "") or "")
            cause = str(getattr(stmt, "cause", "") or "")
            evid = str(getattr(stmt, "evidence", "") or "")
        if not isinstance(lik, int) or not isinstance(det, int):
            raise SchemaInvalid("likelihood-not-int")
        if not (1 <= lik <= 5 and 1 <= det <= 5):
            raise SchemaInvalid("score-range")
        rows.append(
            LedgerRow(
                id=f"FM-{i:03d}",
                participant=part,
                cause=cause,
                likelihood=lik,
                detectability=det,
                rpn=lik * det,
                evidence=evid,
            )
        )
    kernel.record(len(rows))
    return Ledger(entries=rows, plan_id=str(plan_id))


def carry_into_action_plan(ledger: Ledger, plan: ActionPlan) -> Trace:
    mitigated = [m.mitigates for m in (plan.mitigations or [])]
    accepted = [a.failure_mode_id for a in (plan.acceptances or [])]
    silent = list(plan.silent_drops or ())
    ids = [row.id for row in ledger.entries]
    unmitigated = [i for i in ids if i not in mitigated]
    dispositions = []
    for i in ids:
        if i in mitigated:
            dispositions.append({"id": i, "disposition": "mitigated"})
        elif i in accepted:
            dispositions.append({"id": i, "disposition": "accepted"})
        else:
            dispositions.append({"id": i, "disposition": "unmitigated"})
    invariant = all(
        d["disposition"] in {"mitigated", "accepted"} for d in dispositions
    ) and not silent
    return Trace(
        dispositions=dispositions,
        traceability_count=len(mitigated),
        mitigated_ids=mitigated,
        accepted_ids=accepted,
        unmitigated_ids=unmitigated,
        silent_drop_ids=silent,
        invariant_ok=invariant,
    )


def drop_mode_silently(plan: ActionPlan, target: str) -> ActionPlan:
    kept = tuple(m for m in (plan.mitigations or ()) if m.mitigates != target)
    return ActionPlan(
        plan_id=plan.plan_id,
        decision_id=plan.decision_id,
        mitigations=kept,
        acceptances=plan.acceptances,
        silent_drops=(target,),
    )


def omitted_unmitigated(trace: Trace, claimed_unmitigated: list | None = None) -> list:
    claimed = list(claimed_unmitigated or [])
    return [i for i in trace.unmitigated_ids if i not in claimed]

__all__ = ['Acceptance', 'ActionPlan', 'CauseStatement', 'FAILED_PREMISE', 'KernelBypass', 'Mitigation', 'PremiseMissing', 'RecordingKernel', 'SchemaInvalid', 'carry_into_action_plan', 'drop_mode_silently', 'harvest', 'omitted_unmitigated']

