"""Premortem protocol with a structured failure-mode ledger (P43, IMP-0336).

A premortem starts from the assertion that the plan has *already failed*
(:data:`FAILED_PREMISE`) and asks every participant for the cause.  The causes
are harvested into a typed ledger - one :class:`FailureMode` per statement with
integer ``likelihood`` and ``detectability`` on a 1..5 scale and their product
``rpn`` - and every harvest step is a kernel turn (the premise assertion plus
one turn per cause), so ``turns_recorded == turns_executed == 1 + causes``.

The falsifiable question is whether harvested failure modes are ever carried
into the action plan or merely *collected and dropped*.  The answer is computed
by :func:`carry_into_action_plan`, which binds every ledger id to the plan's
:class:`Mitigation` rows (``mitigates`` must name a ledger id) and
:class:`Acceptance` rows (an explicit, owned decision not to mitigate).  The
resulting :class:`Trace` reports ``traceability_count`` (mitigated rows),
``unmitigated_ids`` (rows without a mitigation, accepted ones included so they
are listed rather than omitted), ``silent_drop_ids`` (rows neither mitigated
nor accepted) and ``invariant_ok`` - every row is mitigated or explicitly
accepted.  :func:`drop_mode_silently` is the adversarial mutant: it removes a
mode's mitigation and acceptance, which makes the count *fall* and the
invariant fire.  :func:`omitted_unmitigated` catches a report that claims a
shorter unmitigated list than the trace computed.

Refusals are typed: :class:`PremiseMissing` (the plan "might work"),
:class:`SchemaInvalid` (``likelihood-not-int``, ``empty-harvest``,
``orphan-mitigation`` ...) and :class:`KernelBypass` (``kernel=None`` or a
kernel that executes without recording).  The module never opens a write
handle on participant output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "PROTOCOL_ID",
    "FAILED_PREMISE",
    "SCALE_MIN",
    "SCALE_MAX",
    "DISPOSITION_MITIGATED",
    "DISPOSITION_ACCEPTED",
    "DISPOSITION_DROPPED",
    "PremortemError",
    "PremiseMissing",
    "SchemaInvalid",
    "KernelBypass",
    "RecordingKernel",
    "CauseStatement",
    "FailureMode",
    "FailureModeLedger",
    "Mitigation",
    "Acceptance",
    "ActionPlan",
    "Trace",
    "premise_asserts_failure",
    "harvest",
    "carry_into_action_plan",
    "drop_mode_silently",
    "omitted_unmitigated",
]

PROTOCOL_ID = "P43-premortem"
FAILED_PREMISE = "The plan has already failed."
SCALE_MIN = 1
SCALE_MAX = 5
DISPOSITION_MITIGATED = "mitigated"
DISPOSITION_ACCEPTED = "accepted"
DISPOSITION_DROPPED = "dropped"
_PREMISE_CUES = ("already failed", "has failed", "did fail", "failed")


class PremortemError(ValueError):
    """Base class for premortem refusals."""


class PremiseMissing(PremortemError):
    """The harvest was not framed as 'the plan has already failed'."""


class SchemaInvalid(PremortemError):
    """A ledger or plan row violates the typed schema."""


class KernelBypass(PremortemError):
    """A harvest step would run outside the kernel's execute-and-record loop."""


# -------------------------------------------------------------------------- kernel
class RecordingKernel:
    """Minimal execute-and-record turn sink (IMP-0264 loop invariant)."""

    def __init__(self, council_id: str = "premortem") -> None:
        self.council_id = council_id
        self.turns_executed = 0
        self.turns_recorded = 0
        self.events: list[dict[str, Any]] = []

    def execute_turn(
        self,
        participant_id: str,
        output: str,
        fields: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.turns_executed += 1
        return self.record_turn(participant_id, output, fields)

    def record_turn(
        self,
        participant_id: str,
        output: str,
        fields: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "kind": "TURN",
            "seq": self.turns_recorded + 1,
            "participant_id": participant_id,
            "status": "ok",
            "output": output,
            "fields": dict(fields or {}),
        }
        self.events.append(event)
        self.turns_recorded += 1
        return event

    @property
    def invariant_ok(self) -> bool:
        return self.turns_executed == self.turns_recorded


# -------------------------------------------------------------------------- ledger
@dataclass(frozen=True)
class CauseStatement:
    """One participant's answer to 'why did the plan fail?'."""

    participant: str
    cause: str
    likelihood: int
    detectability: int
    evidence: str = ""


@dataclass(frozen=True)
class FailureMode:
    """One typed ledger row (``rpn = likelihood * detectability``)."""

    id: str
    sequence: int
    participant: str
    cause: str
    likelihood: int
    detectability: int
    rpn: int
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sequence": self.sequence,
            "participant": self.participant,
            "cause": self.cause,
            "likelihood": self.likelihood,
            "detectability": self.detectability,
            "rpn": self.rpn,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class FailureModeLedger:
    """Harvest result: plan id, the failed premise, typed rows, kernel events."""

    plan_id: str
    premise: str
    entries: tuple[FailureMode, ...]
    turn_events: tuple[dict[str, Any], ...] = ()
    protocol_id: str = PROTOCOL_ID

    def ids(self) -> tuple[str, ...]:
        return tuple(row.id for row in self.entries)

    def by_id(self) -> dict[str, FailureMode]:
        return {row.id: row for row in self.entries}

    def ranked(self) -> tuple[FailureMode, ...]:
        """Rows by descending RPN, ties in harvest order."""
        return tuple(sorted(self.entries, key=lambda row: (-row.rpn, row.sequence)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "premise": self.premise,
            "protocol_id": self.protocol_id,
            "entries": [row.to_dict() for row in self.entries],
            "turns": len(self.turn_events),
        }


def _norm(text: Any) -> str:
    return " ".join(str(text).lower().replace("'", "").split()).rstrip(" .!")


def premise_asserts_failure(premise: Any) -> bool:
    """True when the premise states the plan has already failed (not 'might')."""
    text = _norm(premise)
    if not text:
        return False
    if text == _norm(FAILED_PREMISE):
        return True
    hedged = any(word in text.split() for word in ("might", "may", "could", "if", "unless"))
    return (not hedged) and any(cue in text for cue in _PREMISE_CUES)


def _score(value: Any, name: str, row: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaInvalid(f"{name}-not-int: statement {row} {name}={value!r}")
    if not SCALE_MIN <= value <= SCALE_MAX:
        raise SchemaInvalid(
            f"{name}-out-of-range: statement {row} {name}={value} not in {SCALE_MIN}..{SCALE_MAX}"
        )
    return value


def _as_statement(item: Any, row: int) -> CauseStatement:
    if isinstance(item, CauseStatement):
        data: dict[str, Any] = {
            "participant": item.participant,
            "cause": item.cause,
            "likelihood": item.likelihood,
            "detectability": item.detectability,
            "evidence": item.evidence,
        }
    elif isinstance(item, Mapping):
        data = dict(item)
    else:
        raise SchemaInvalid(f"statement-not-typed: statement {row} is {type(item).__name__}")
    for key in ("participant", "cause", "likelihood", "detectability"):
        if key not in data:
            raise SchemaInvalid(f"missing-{key}: statement {row}")
    participant = str(data["participant"]).strip()
    cause = str(data["cause"]).strip()
    if not participant:
        raise SchemaInvalid(f"empty-participant: statement {row}")
    if not cause:
        raise SchemaInvalid(f"empty-cause: statement {row}")
    return CauseStatement(
        participant=participant,
        cause=cause,
        likelihood=_score(data["likelihood"], "likelihood", row),
        detectability=_score(data["detectability"], "detectability", row),
        evidence=str(data.get("evidence") or ""),
    )


def _turn(kernel: Any, participant: str, output: str, fields: dict[str, Any]) -> dict[str, Any]:
    before = (getattr(kernel, "turns_executed", None), getattr(kernel, "turns_recorded", None))
    if hasattr(kernel, "execute_turn"):
        event = kernel.execute_turn(participant, output, fields)
    elif hasattr(kernel, "record_turn"):
        event = kernel.record_turn(participant, output, fields)
    else:
        raise KernelBypass("kernel exposes neither execute_turn nor record_turn")
    executed = getattr(kernel, "turns_executed", None)
    recorded = getattr(kernel, "turns_recorded", None)
    if executed is not None and recorded is not None and executed != recorded:
        raise KernelBypass("kernel executed a turn it did not record")
    if recorded is not None and before[1] is not None and recorded == before[1]:
        raise KernelBypass("kernel recorded nothing for the premortem turn")
    return event if isinstance(event, dict) else {"participant_id": participant, "output": output}


def harvest(
    plan_id: str,
    premise: str,
    statements: Iterable[Any],
    kernel: Any,
    chair: str = "chair",
) -> FailureModeLedger:
    """Harvest cause statements into a typed ledger through kernel turns.

    Raises :class:`PremiseMissing` unless ``premise`` asserts the plan has
    already failed, :class:`KernelBypass` without a kernel, and
    :class:`SchemaInvalid` for an empty harvest or an untyped/out-of-range row.
    Ledger ids are ``FM-001`` ... in statement order; each row costs one turn
    after the chair's premise turn.
    """
    plan = str(plan_id).strip()
    if not plan:
        raise SchemaInvalid("empty-plan-id")
    if not premise_asserts_failure(premise):
        raise PremiseMissing(
            f"premise must assert the plan has already failed, got {str(premise)!r}"
        )
    if kernel is None:
        raise KernelBypass("harvest requires a kernel turn sink; kernel=None")
    typed = [_as_statement(item, i + 1) for i, item in enumerate(statements)]
    if not typed:
        raise SchemaInvalid("empty-harvest: no cause statements")
    events = [
        _turn(kernel, chair, str(premise), {"kind": "premise", "plan_id": plan, "protocol_id": PROTOCOL_ID})
    ]
    rows: list[FailureMode] = []
    for i, stmt in enumerate(typed, 1):
        mode_id = f"FM-{i:03d}"
        events.append(
            _turn(
                kernel,
                stmt.participant,
                stmt.cause,
                {
                    "kind": "cause",
                    "plan_id": plan,
                    "failure_mode_id": mode_id,
                    "likelihood": stmt.likelihood,
                    "detectability": stmt.detectability,
                },
            )
        )
        rows.append(
            FailureMode(
                id=mode_id,
                sequence=i,
                participant=stmt.participant,
                cause=stmt.cause,
                likelihood=stmt.likelihood,
                detectability=stmt.detectability,
                rpn=stmt.likelihood * stmt.detectability,
                evidence=stmt.evidence,
            )
        )
    return FailureModeLedger(
        plan_id=plan, premise=str(premise), entries=tuple(rows), turn_events=tuple(events)
    )


# ---------------------------------------------------------------------------- plan
@dataclass(frozen=True)
class Mitigation:
    """An action bound to one ledger id (``mitigates``)."""

    id: str
    mitigates: str
    owner: str
    precondition: str = ""
    verification: str = ""
    mechanism: str = ""
    sequence: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mitigates": self.mitigates,
            "owner": self.owner,
            "precondition": self.precondition,
            "verification": self.verification,
            "mechanism": self.mechanism,
            "sequence": self.sequence,
        }


@dataclass(frozen=True)
class Acceptance:
    """An explicit, owned decision not to mitigate a failure mode."""

    failure_mode_id: str
    owner: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_mode_id": self.failure_mode_id,
            "owner": self.owner,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ActionPlan:
    plan_id: str
    decision_id: str
    mitigations: tuple[Mitigation, ...] = ()
    acceptances: tuple[Acceptance, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "mitigations", tuple(self.mitigations))
        object.__setattr__(self, "acceptances", tuple(self.acceptances))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "decision_id": self.decision_id,
            "mitigations": [m.to_dict() for m in self.mitigations],
            "acceptances": [a.to_dict() for a in self.acceptances],
        }


@dataclass(frozen=True)
class Trace:
    """Result of binding a ledger to an action plan."""

    plan_id: str
    decision_id: str
    ledger_ids: tuple[str, ...]
    mitigated_ids: tuple[str, ...]
    accepted_ids: tuple[str, ...]
    unmitigated_ids: tuple[str, ...]
    silent_drop_ids: tuple[str, ...]
    dispositions: tuple[dict[str, Any], ...]
    traceability_count: int
    invariant_ok: bool
    violations: tuple[str, ...] = field(default=())

    @property
    def ledger_entries(self) -> int:
        return len(self.ledger_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "decision_id": self.decision_id,
            "ledger_entries": self.ledger_entries,
            "traceability_count": self.traceability_count,
            "mitigated_ids": list(self.mitigated_ids),
            "accepted_ids": list(self.accepted_ids),
            "unmitigated_ids": list(self.unmitigated_ids),
            "silent_drop_ids": list(self.silent_drop_ids),
            "invariant_ok": self.invariant_ok,
            "violations": list(self.violations),
            "dispositions": list(self.dispositions),
        }


def _check_plan_rows(ledger: FailureModeLedger, plan: ActionPlan) -> None:
    known = set(ledger.ids())
    if str(plan.plan_id) != ledger.plan_id:
        raise SchemaInvalid(
            f"plan-mismatch: ledger {ledger.plan_id!r} vs action plan {plan.plan_id!r}"
        )
    seen_ids: set[str] = set()
    for m in plan.mitigations:
        if not isinstance(m, Mitigation):
            raise SchemaInvalid(f"mitigation-not-typed: {type(m).__name__}")
        if not str(m.id).strip():
            raise SchemaInvalid("mitigation-missing-id")
        if m.id in seen_ids:
            raise SchemaInvalid(f"duplicate-mitigation-id: {m.id}")
        seen_ids.add(m.id)
        if not str(m.owner).strip():
            raise SchemaInvalid(f"mitigation-missing-owner: {m.id}")
        if m.mitigates not in known:
            raise SchemaInvalid(f"orphan-mitigation: {m.id} mitigates {m.mitigates!r} not in ledger")
    for a in plan.acceptances:
        if not isinstance(a, Acceptance):
            raise SchemaInvalid(f"acceptance-not-typed: {type(a).__name__}")
        if a.failure_mode_id not in known:
            raise SchemaInvalid(f"orphan-acceptance: {a.failure_mode_id!r} not in ledger")
        if not str(a.owner).strip():
            raise SchemaInvalid(f"acceptance-missing-owner: {a.failure_mode_id}")
        if not str(a.rationale).strip():
            raise SchemaInvalid(f"acceptance-missing-rationale: {a.failure_mode_id}")


def carry_into_action_plan(ledger: FailureModeLedger, plan: ActionPlan) -> Trace:
    """Bind every ledger row to the plan and compute the traceability trace.

    ``traceability_count`` counts ledger rows with at least one mitigation.
    ``unmitigated_ids`` lists every row without a mitigation (explicitly
    accepted rows included, so nothing is omitted from the report);
    ``silent_drop_ids`` are rows neither mitigated nor accepted, and the
    invariant holds only when that list is empty.
    """
    _check_plan_rows(ledger, plan)
    mitigations_for: dict[str, list[str]] = {}
    for m in sorted(plan.mitigations, key=lambda x: (x.sequence, x.id)):
        mitigations_for.setdefault(m.mitigates, []).append(m.id)
    acceptance_for: dict[str, Acceptance] = {}
    for a in plan.acceptances:
        acceptance_for.setdefault(a.failure_mode_id, a)

    mitigated: list[str] = []
    accepted: list[str] = []
    unmitigated: list[str] = []
    dropped: list[str] = []
    dispositions: list[dict[str, Any]] = []
    violations: list[str] = []
    for row in ledger.entries:
        acts = mitigations_for.get(row.id, [])
        acc = acceptance_for.get(row.id)
        if acts:
            disposition = DISPOSITION_MITIGATED
            mitigated.append(row.id)
        elif acc is not None:
            disposition = DISPOSITION_ACCEPTED
            accepted.append(row.id)
            unmitigated.append(row.id)
        else:
            disposition = DISPOSITION_DROPPED
            unmitigated.append(row.id)
            dropped.append(row.id)
            violations.append(f"silent-drop: {row.id} neither mitigated nor accepted")
        dispositions.append(
            {
                "id": row.id,
                "cause": row.cause,
                "rpn": row.rpn,
                "disposition": disposition,
                "mitigation_ids": list(acts),
                "acceptance_owner": acc.owner if acc is not None else None,
            }
        )
    return Trace(
        plan_id=ledger.plan_id,
        decision_id=str(plan.decision_id),
        ledger_ids=ledger.ids(),
        mitigated_ids=tuple(mitigated),
        accepted_ids=tuple(accepted),
        unmitigated_ids=tuple(unmitigated),
        silent_drop_ids=tuple(dropped),
        dispositions=tuple(dispositions),
        traceability_count=len(mitigated),
        invariant_ok=not dropped,
        violations=tuple(violations),
    )


def drop_mode_silently(plan: ActionPlan, failure_mode_id: str) -> ActionPlan:
    """Adversarial mutant: remove a mode's mitigations *and* acceptance.

    Nothing replaces them, which is exactly the collected-and-dropped failure.
    Raises :class:`PremortemError` when the plan never referenced the id (the
    mutant would equal the original and prove nothing).
    """
    mitigations = tuple(m for m in plan.mitigations if m.mitigates != failure_mode_id)
    acceptances = tuple(a for a in plan.acceptances if a.failure_mode_id != failure_mode_id)
    if len(mitigations) == len(plan.mitigations) and len(acceptances) == len(plan.acceptances):
        raise PremortemError(f"nothing-to-drop: {failure_mode_id!r} is not referenced by the plan")
    return ActionPlan(
        plan_id=plan.plan_id,
        decision_id=plan.decision_id,
        mitigations=mitigations,
        acceptances=acceptances,
    )


def omitted_unmitigated(trace: Trace, claimed_unmitigated: Sequence[str]) -> list[str]:
    """Unmitigated ids the trace computed that a report failed to list."""
    claimed = {str(x) for x in claimed_unmitigated}
    return [mode_id for mode_id in trace.unmitigated_ids if mode_id not in claimed]
