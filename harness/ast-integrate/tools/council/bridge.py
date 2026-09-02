"""Council-as-a-workflow-stage bridge (IMP-0344).

A workflow composes ``compute`` stages and ``council`` stages. The workflow
owns exactly one control plane — one ``Scheduler`` and one append-only
``EventLog`` — and the council is *invoked* on that plane: ``CouncilBridge.invoke``
never constructs a plane of its own (``invoke_constructs_control_plane`` is the
AST sweep that proves it). Every ``EventLog``/``Scheduler`` constructed while a
run is in flight is counted by the run census, so a second plane built by an
invoker is detected as ``duplicate-control-plane``.

Council failures are classified under the *workflow's* failure policy, a
closed taxonomy (``FAILURE_FAMILIES``) mapped to actions. A policy naming a
family outside the taxonomy fails closed (``PolicyValidationError``). A council
that writes ``council.turn.failed`` and still returns a decided outcome is a
swallowed failure: the bridge classifies it (family ``swallowed-failure``) and
``detect_swallowed_council_failure`` finds any ``council.turn.failed`` event the
workflow never classified.
"""

from __future__ import annotations

import ast
import itertools
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Protocol

# --------------------------------------------------------------------------- #
# failure taxonomy / policy
# --------------------------------------------------------------------------- #
FAILURE_FAMILIES: tuple[str, ...] = (
    "model-error",
    "timeout",
    "protocol-violation",
    "invalid-output",
    "swallowed-failure",
    "duplicate-control-plane",
    "stage-exception",
    "budget-exhausted",
)
ACTIONS: tuple[str, ...] = ("abort", "retry", "skip", "escalate")
POLICY_SOURCE = "workflow.failure_policy"


class PolicyValidationError(ValueError):
    """A failure policy is incomplete, names an unknown family or action."""


def validate_failure_policy(policy: Any) -> dict[str, str]:
    if not isinstance(policy, dict):
        raise PolicyValidationError(f"failure policy must be a dict, got {type(policy).__name__}")
    unknown = sorted(str(k) for k in policy if k not in FAILURE_FAMILIES)
    if unknown:
        raise PolicyValidationError(
            f"failure policy names families outside the taxonomy: {unknown}"
        )
    missing = [f for f in FAILURE_FAMILIES if f not in policy]
    if missing:
        raise PolicyValidationError(f"failure policy is incomplete; missing families: {missing}")
    bad = {k: v for k, v in policy.items() if v not in ACTIONS}
    if bad:
        raise PolicyValidationError(f"failure policy has unknown actions: {bad}; allowed {ACTIONS}")
    return {k: str(policy[k]) for k in FAILURE_FAMILIES}


def complete_policy(overrides: dict[str, str] | None = None) -> dict[str, str]:
    """A policy covering every family (default action ``abort``), validated."""
    policy = {family: "abort" for family in FAILURE_FAMILIES}
    if overrides:
        policy.update(overrides)
    return validate_failure_policy(policy)


# --------------------------------------------------------------------------- #
# control plane: event log + scheduler, with a construction registry
# --------------------------------------------------------------------------- #
_CONSTRUCTED: list[tuple[str, str]] = []  # (kind, id) in construction order
_ids = itertools.count(1)


def _registry_mark() -> int:
    return len(_CONSTRUCTED)


def _constructed_since(mark: int, kind: str) -> list[str]:
    return [ident for k, ident in _CONSTRUCTED[mark:] if k == kind]


@dataclass(frozen=True)
class Event:
    seq: int
    kind: str
    payload: dict[str, Any]
    plane_id: str
    log_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "payload": dict(self.payload),
            "plane_id": self.plane_id,
            "log_id": self.log_id,
        }


class EventLog:
    """Append-only event log. Construction is registered for the run census."""

    def __init__(self, plane_id: str, log_id: str | None = None) -> None:
        self.plane_id = str(plane_id)
        self.log_id = str(log_id or f"log-{next(_ids)}")
        self.scheduler_id: str | None = None
        self._events: list[Event] = []
        _CONSTRUCTED.append(("event_log", self.log_id))

    @property
    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)

    @property
    def next_seq(self) -> int:
        return len(self._events) + 1

    def bind_scheduler(self, scheduler_id: str) -> None:
        if self.scheduler_id is not None and self.scheduler_id != scheduler_id:
            raise ValueError(
                f"event log {self.log_id} already bound to scheduler {self.scheduler_id}"
            )
        self.scheduler_id = str(scheduler_id)

    def append(self, kind: str, **payload: Any) -> Event:
        event = Event(
            seq=self.next_seq,
            kind=str(kind),
            payload=dict(payload),
            plane_id=self.plane_id,
            log_id=self.log_id,
        )
        self._events.append(event)
        return event

    def __len__(self) -> int:
        return len(self._events)


class Scheduler:
    """Orders stages on one plane. Construction is registered for the census."""

    def __init__(self, plane_id: str, scheduler_id: str | None = None) -> None:
        self.plane_id = str(plane_id)
        self.scheduler_id = str(scheduler_id or f"sched-{next(_ids)}")
        self.queue: list[str] = []
        self.dispatched: list[str] = []
        _CONSTRUCTED.append(("scheduler", self.scheduler_id))

    def schedule(self, stage_ids: Iterable[str]) -> None:
        self.queue.extend(str(s) for s in stage_ids)

    def next_stage(self) -> str | None:
        if not self.queue:
            return None
        stage_id = self.queue.pop(0)
        self.dispatched.append(stage_id)
        return stage_id


class ControlPlane:
    def __init__(self, plane_id: str | None = None) -> None:
        self.id = str(plane_id or f"plane-{next(_ids)}")
        self.event_log = EventLog(plane_id=self.id)
        self.scheduler = Scheduler(plane_id=self.id)
        self.event_log.bind_scheduler(self.scheduler.scheduler_id)


# --------------------------------------------------------------------------- #
# council-side types
# --------------------------------------------------------------------------- #
class CouncilFailed(Exception):
    """An honest council failure, tagged with its taxonomy family."""

    def __init__(self, family: str, message: str = "") -> None:
        self.family = str(family)
        self.message = str(message)
        super().__init__(f"{self.family}: {self.message}" if message else self.family)


@dataclass(frozen=True)
class ClassifiedFailure:
    family: str
    action: str
    source: str
    stage_id: str
    message: str = ""
    ref_seq: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "action": self.action,
            "source": self.source,
            "stage_id": self.stage_id,
            "message": self.message,
            "ref_seq": self.ref_seq,
        }


@dataclass
class CouncilStageInput:
    question: str
    evidence: tuple[str, ...] = ()
    roster: tuple[str, ...] = ()
    protocol: str = "blind_first"
    stage_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "evidence": list(self.evidence),
            "roster": list(self.roster),
            "protocol": self.protocol,
            "stage_id": self.stage_id,
        }


@dataclass
class CouncilDecision:
    outcome: str  # "decided" | "no-decision" | "failed"
    verdict: str
    dissenting: tuple[str, ...] = ()
    plane_id: str = ""
    source_stage: str = ""
    classified_failure: ClassifiedFailure | None = None
    votes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "verdict": self.verdict,
            "dissenting": list(self.dissenting),
            "plane_id": self.plane_id,
            "source_stage": self.source_stage,
            "classified_failure": None
            if self.classified_failure is None
            else self.classified_failure.to_dict(),
            "votes": dict(self.votes),
        }


class Invoker(Protocol):
    def run(self, payload: CouncilStageInput, plane: ControlPlane) -> CouncilDecision: ...


SUPPORTED_PROTOCOLS = ("blind_first", "sequential", "chair")
_OBJECTION_MARKERS = ("reject", "block", "veto", "deny", "unsafe", "regression", "do not")


class DeterministicInvoker:
    """Built-in council: every seat votes on the plane's log; majority decides.

    A seat dissents when the evidence it is shown carries an objection marker;
    the record of each turn is written to the *given* plane, never to a new one.
    """

    def run(self, payload: CouncilStageInput, plane: ControlPlane) -> CouncilDecision:
        if payload.protocol not in SUPPORTED_PROTOCOLS:
            plane.event_log.append(
                "council.turn.failed",
                stage_id=payload.stage_id,
                family="protocol-violation",
                message=f"unknown protocol {payload.protocol!r}",
            )
            raise CouncilFailed("protocol-violation", f"unknown protocol {payload.protocol!r}")
        if not payload.roster:
            plane.event_log.append(
                "council.turn.failed",
                stage_id=payload.stage_id,
                family="invalid-output",
                message="empty roster",
            )
            raise CouncilFailed("invalid-output", "empty roster")
        text = " ".join([payload.question, *payload.evidence]).casefold()
        objection = any(marker in text for marker in _OBJECTION_MARKERS)
        votes: dict[str, str] = {}
        for seat in payload.roster:
            vote = "reject" if objection else "approve"
            votes[seat] = vote
            plane.event_log.append(
                "council.turn.completed",
                stage_id=payload.stage_id,
                seat=seat,
                vote=vote,
                protocol=payload.protocol,
            )
        approve = sum(1 for v in votes.values() if v == "approve")
        reject = len(votes) - approve
        if approve == reject:
            verdict, outcome = "tie", "no-decision"
        else:
            verdict, outcome = ("approve" if approve > reject else "reject"), "decided"
        dissenting = tuple(s for s, v in votes.items() if v != verdict)
        plane.event_log.append(
            "council.vote.tallied",
            stage_id=payload.stage_id,
            approve=approve,
            reject=reject,
            verdict=verdict,
        )
        return CouncilDecision(
            outcome=outcome,
            verdict=verdict,
            dissenting=dissenting,
            plane_id=plane.id,
            source_stage=payload.stage_id,
            votes=votes,
        )


# --------------------------------------------------------------------------- #
# the bridge
# --------------------------------------------------------------------------- #
class CouncilBridge:
    """Invokes a council on the workflow's plane and classifies its failures."""

    def __init__(self, invoker: Invoker | None = None) -> None:
        self.invoker: Invoker = invoker if invoker is not None else DeterministicInvoker()

    def invoke(
        self,
        payload: CouncilStageInput,
        plane: ControlPlane,
        policy: dict[str, str],
        stage_id: str,
    ) -> CouncilDecision:
        log = plane.event_log
        payload = replace(payload, stage_id=stage_id)
        first_seq = log.next_seq
        try:
            decision = self.invoker.run(payload, plane)
        except CouncilFailed as exc:
            return self.classify(exc.family, exc.message, plane, policy, stage_id, first_seq)
        except Exception as exc:  # noqa: BLE001 - every exception becomes a classified failure
            return self.classify(
                "stage-exception", f"{type(exc).__name__}: {exc}", plane, policy, stage_id, first_seq
            )
        if not isinstance(decision, CouncilDecision):
            return self.classify(
                "invalid-output",
                f"invoker returned {type(decision).__name__}, not CouncilDecision",
                plane,
                policy,
                stage_id,
                first_seq,
            )
        unclassified = [
            e
            for e in log.events
            if e.seq >= first_seq and e.kind == "council.turn.failed"
        ]
        if unclassified and decision.outcome != "failed":
            first = unclassified[0]
            return self.classify(
                "swallowed-failure",
                f"council wrote {len(unclassified)} council.turn.failed event(s) "
                f"(first: {first.payload.get('family')}: {first.payload.get('message')}) "
                f"yet returned outcome={decision.outcome!r}",
                plane,
                policy,
                stage_id,
                first_seq,
            )
        if decision.plane_id != plane.id:
            return self.classify(
                "invalid-output",
                f"decision claims plane {decision.plane_id!r}, invoked on {plane.id!r}",
                plane,
                policy,
                stage_id,
                first_seq,
            )
        return decision

    @staticmethod
    def classify(
        family: str,
        message: str,
        plane: ControlPlane,
        policy: dict[str, str],
        stage_id: str,
        first_seq: int,
    ) -> CouncilDecision:
        if family not in FAILURE_FAMILIES:
            message = f"[reported family {family!r} is outside the taxonomy] {message}"
            family = "protocol-violation"
        action = policy[family]
        log = plane.event_log
        failed = [
            e
            for e in log.events
            if e.seq >= first_seq and e.kind == "council.turn.failed"
        ]
        ref_seq = failed[0].seq if failed else None
        if ref_seq is None:
            ref_seq = log.append(
                "council.turn.failed", stage_id=stage_id, family=family, message=message
            ).seq
        log.append(
            "workflow.failure.classified",
            family=family,
            action=action,
            stage_id=stage_id,
            source=POLICY_SOURCE,
            ref_seq=ref_seq,
            message=message,
        )
        classified = ClassifiedFailure(
            family=family,
            action=action,
            source=POLICY_SOURCE,
            stage_id=stage_id,
            message=message,
            ref_seq=ref_seq,
        )
        return CouncilDecision(
            outcome="failed",
            verdict=family,
            dissenting=(),
            plane_id=plane.id,
            source_stage=stage_id,
            classified_failure=classified,
        )


# --------------------------------------------------------------------------- #
# workflow
# --------------------------------------------------------------------------- #
STAGE_KINDS = ("compute", "council")


@dataclass
class StageSpec:
    id: str
    kind: str
    output_key: str
    on_failure: dict[str, str]
    compute: Callable[[dict[str, Any]], Any] | None = None
    council_input: Callable[[dict[str, Any]], CouncilStageInput] | None = None

    def __post_init__(self) -> None:
        if self.kind not in STAGE_KINDS:
            raise ValueError(f"stage {self.id!r}: unknown kind {self.kind!r}; allowed {STAGE_KINDS}")
        if self.kind == "compute" and self.compute is None:
            raise ValueError(f"stage {self.id!r}: compute stage needs a compute callable")
        if self.kind == "council" and self.council_input is None:
            raise ValueError(f"stage {self.id!r}: council stage needs a council_input callable")
        self.on_failure = validate_failure_policy(self.on_failure)


@dataclass(frozen=True)
class Census:
    event_log_count: int
    scheduler_count: int
    event_log_ids: tuple[str, ...] = ()
    scheduler_ids: tuple[str, ...] = ()

    @property
    def single_control_plane(self) -> bool:
        return self.event_log_count == 1 and self.scheduler_count == 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_log_count": self.event_log_count,
            "scheduler_count": self.scheduler_count,
            "event_log_ids": list(self.event_log_ids),
            "scheduler_ids": list(self.scheduler_ids),
            "single_control_plane": self.single_control_plane,
        }


@dataclass
class WorkflowResult:
    status: str
    context: dict[str, Any]
    plane: ControlPlane
    census: Census
    classifications: list[ClassifiedFailure] = field(default_factory=list)
    duplicate_control_plane: bool = False
    stages_completed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "census": self.census.to_dict(),
            "classifications": [c.to_dict() for c in self.classifications],
            "duplicate_control_plane": self.duplicate_control_plane,
            "stages_completed": list(self.stages_completed),
            "events": [e.to_dict() for e in self.plane.event_log.events],
        }


class WorkflowRunner:
    def __init__(self, stages: Iterable[StageSpec], invoker: Invoker | None = None) -> None:
        self.stages = list(stages)
        ids = [s.id for s in self.stages]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate stage ids: {ids}")
        self.bridge = CouncilBridge(invoker)

    def _census(self, mark: int) -> Census:
        logs = _constructed_since(mark, "event_log")
        scheds = _constructed_since(mark, "scheduler")
        return Census(
            event_log_count=len(logs),
            scheduler_count=len(scheds),
            event_log_ids=tuple(logs),
            scheduler_ids=tuple(scheds),
        )

    def run(self, context: dict[str, Any] | None = None) -> WorkflowResult:
        ctx: dict[str, Any] = dict(context or {})
        mark = _registry_mark()
        plane = ControlPlane()
        log = plane.event_log
        plane.scheduler.schedule(s.id for s in self.stages)
        log.append("workflow.started", plane_id=plane.id, stages=[s.id for s in self.stages])

        status = "SUCCESS"
        classifications: list[ClassifiedFailure] = []
        completed: list[str] = []
        duplicate = False
        halted = False

        while not halted:
            stage_id = plane.scheduler.next_stage()
            if stage_id is None:
                break
            stage = next(s for s in self.stages if s.id == stage_id)
            log.append("workflow.stage.started", stage_id=stage.id, stage_kind=stage.kind)
            failure: ClassifiedFailure | None = None
            attempts = 0
            while True:
                attempts += 1
                failure = self._run_stage(stage, ctx, plane)
                if failure is not None and failure.action == "retry" and attempts == 1:
                    log.append("workflow.stage.retried", stage_id=stage.id, family=failure.family)
                    continue
                break
            planes_now = self._census(mark)
            if not duplicate and planes_now.event_log_count > 1:
                duplicate = True
                dup = ClassifiedFailure(
                    family="duplicate-control-plane",
                    action=stage.on_failure["duplicate-control-plane"],
                    source=POLICY_SOURCE,
                    stage_id=stage.id,
                    message=(
                        f"{planes_now.event_log_count} event logs constructed during the run: "
                        f"{list(planes_now.event_log_ids)}"
                    ),
                )
                log.append(
                    "workflow.failure.classified",
                    family=dup.family,
                    action=dup.action,
                    stage_id=stage.id,
                    source=POLICY_SOURCE,
                    ref_seq=None,
                    message=dup.message,
                )
                classifications.append(dup)
                status = "FAILED"
                if dup.action in ("abort", "escalate"):
                    halted = True
            if failure is not None:
                classifications.append(failure)
                status = "FAILED"
                log.append(
                    "workflow.stage.failed", stage_id=stage.id, family=failure.family, action=failure.action
                )
                if failure.action == "escalate":
                    log.append("workflow.escalated", stage_id=stage.id, family=failure.family)
                if failure.action in ("abort", "escalate", "retry"):
                    halted = True
                continue
            completed.append(stage.id)
            log.append("workflow.stage.completed", stage_id=stage.id, output_key=stage.output_key)

        census = self._census(mark)
        log.append("workflow.finished", status=status, census=census.to_dict())
        return WorkflowResult(
            status=status,
            context=ctx,
            plane=plane,
            census=census,
            classifications=classifications,
            duplicate_control_plane=duplicate,
            stages_completed=completed,
        )

    def _run_stage(
        self, stage: StageSpec, ctx: dict[str, Any], plane: ControlPlane
    ) -> ClassifiedFailure | None:
        log = plane.event_log
        if stage.kind == "compute":
            assert stage.compute is not None
            try:
                ctx[stage.output_key] = stage.compute(ctx)
            except Exception as exc:  # noqa: BLE001 - classified, never swallowed
                family = "stage-exception"
                action = stage.on_failure[family]
                message = f"{type(exc).__name__}: {exc}"
                log.append(
                    "workflow.failure.classified",
                    family=family,
                    action=action,
                    stage_id=stage.id,
                    source=POLICY_SOURCE,
                    ref_seq=None,
                    message=message,
                )
                return ClassifiedFailure(family, action, POLICY_SOURCE, stage.id, message)
            return None

        assert stage.council_input is not None
        log.append("council.stage.entered", stage_id=stage.id)
        try:
            payload = stage.council_input(ctx)
        except Exception as exc:  # noqa: BLE001
            family = "invalid-output"
            action = stage.on_failure[family]
            message = f"council_input raised {type(exc).__name__}: {exc}"
            log.append(
                "workflow.failure.classified",
                family=family,
                action=action,
                stage_id=stage.id,
                source=POLICY_SOURCE,
                ref_seq=None,
                message=message,
            )
            return ClassifiedFailure(family, action, POLICY_SOURCE, stage.id, message)
        decision = self.bridge.invoke(payload, plane, stage.on_failure, stage.id)
        ctx[stage.output_key] = decision
        log.append(
            "council.stage.exited",
            stage_id=stage.id,
            outcome=decision.outcome,
            verdict=decision.verdict,
        )
        return decision.classified_failure


# --------------------------------------------------------------------------- #
# detectors
# --------------------------------------------------------------------------- #
def detect_swallowed_council_failure(events: Iterable[Event]) -> list[Event]:
    """``council.turn.failed`` events the workflow never classified."""
    evs = list(events)
    classified = [e for e in evs if e.kind == "workflow.failure.classified"]
    by_ref = {e.payload.get("ref_seq") for e in classified if e.payload.get("ref_seq") is not None}
    swallowed: list[Event] = []
    for e in evs:
        if e.kind != "council.turn.failed":
            continue
        if e.seq in by_ref:
            continue
        pair_hit = any(
            c.seq > e.seq
            and c.payload.get("stage_id") == e.payload.get("stage_id")
            and c.payload.get("family") == e.payload.get("family")
            for c in classified
        )
        if not pair_hit:
            swallowed.append(e)
    return swallowed


_PLANE_CONSTRUCTORS = frozenset({"EventLog", "Scheduler", "ControlPlane"})


def invoke_constructs_control_plane(source: str) -> list[str]:
    """AST sweep: list every control-plane construction inside ``CouncilBridge.invoke``.

    Returns ``[]`` when the invariant holds. Fails closed when the class or
    method cannot be found.
    """
    tree = ast.parse(source)
    hits: list[str] = []
    found = False
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "CouncilBridge"):
            continue
        for item in node.body:
            if not (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "invoke"):
                continue
            found = True
            for sub in ast.walk(item):
                if not isinstance(sub, ast.Call):
                    continue
                func = sub.func
                name = func.id if isinstance(func, ast.Name) else (
                    func.attr if isinstance(func, ast.Attribute) else None
                )
                if name in _PLANE_CONSTRUCTORS:
                    hits.append(f"CouncilBridge.invoke:{sub.lineno} constructs {name}")
    if not found:
        hits.append("CouncilBridge.invoke not found in source")
    return hits


__all__ = [
    "ACTIONS",
    "FAILURE_FAMILIES",
    "POLICY_SOURCE",
    "Census",
    "ClassifiedFailure",
    "ControlPlane",
    "CouncilBridge",
    "CouncilDecision",
    "CouncilFailed",
    "CouncilStageInput",
    "DeterministicInvoker",
    "Event",
    "EventLog",
    "PolicyValidationError",
    "Scheduler",
    "StageSpec",
    "WorkflowResult",
    "WorkflowRunner",
    "complete_policy",
    "detect_swallowed_council_failure",
    "invoke_constructs_control_plane",
    "validate_failure_policy",
]
