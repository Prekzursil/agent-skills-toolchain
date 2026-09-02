"""Nested topology: spawn a subcouncil for a bounded question and fold its result back.

Roles (IMP-0288, spec anchor ``_USER-PROMPTS.md:11343`` "nested councils disagree on
completion")
---------------------------------------------------------------------------------------
* ``BoundedQuestion`` -- the one question a child council may be spawned for, with a hard
  round budget. A child artifact that answers a different question, or that ran more
  rounds than the budget, is *unbounded* and ``spawn_subcouncil`` refuses it
  (``UnboundedChildError``) instead of folding it.
* ``spawn_subcouncil`` -- validates the bound, records the child's turns on the kernel and
  asks the shared completion reducer for the child's verdict at the child boundary.
* ``resolve_disagreement`` -- the named rule for parent/child completion disagreement.
* ``run_nested`` -- spawn + judge parent + resolve + fold into a new parent artifact.
* ``run_depth2`` -- two levels: leaf folds into mid, the folded mid folds into grandparent.

Completion
----------
Completion is never read off an artifact's ``self_report_complete`` bit and never
averaged. Every boundary asks exactly one predicate,
``tools.council.shared_completion.judge`` (imported here as ``shared_judge``), so a probe
can re-call the same predicate for an independent recount and an AST check can see that
``_judge_at_child_boundary`` calls it.

Disagreement is resolved by ``RESOLUTION_RULE_ID`` -- conservative conjunction: the folded
completion is COMPLETE iff the child is reducer-COMPLETE at the child boundary AND the
parent is reducer-COMPLETE after the fold. The incomplete side blocks and is named as the
``blocking_party``; the child's minority report and dissent survive verbatim in the folded
parent, and the parent cites the child's evidence when it overrules the child's
self-report. ``apply_resolution_rule=False`` is the negative control: the fold then falls
back to last-writer-wins over ``order`` and labels itself ``incidental`` with no rule id,
which is exactly the nondeterminism the rule exists to remove.

Kernel
------
``InMemoryKernel`` is a local event log standing in for ``tools/council/kernel.py``: the
topology records ``SPAWN``, ``TURN``, ``CHILD_BOUNDARY_JUDGE``, ``PARENT_JUDGE``,
``RESOLUTION`` and ``FOLD`` events there and nowhere else.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from tools.council.shared_completion import (
    REDUCER_MODULE,
    REDUCER_PATH,
    CompletionVerdict,
    judge as shared_judge,
)

SPEC_ANCHOR = "_USER-PROMPTS.md:11343 nested councils disagree on completion"
RESOLUTION_RULE_ID = "nested.disagreement.conservative-conjunction.v1"

PARTY_CHILD = "child"
PARTY_PARENT = "parent"
PARTY_BOTH = "both"
PARTIES = (PARTY_CHILD, PARTY_PARENT)
DEFAULT_ORDER: tuple[str, ...] = (PARTY_CHILD, PARTY_PARENT)

LOCUS_CHILD_BOUNDARY = "child-boundary"
LOCUS_PARENT_AFTER_FOLD = "parent-after-fold"

EVENT_SPAWN = "SPAWN"
EVENT_TURN = "TURN"
EVENT_CHILD_BOUNDARY_JUDGE = "CHILD_BOUNDARY_JUDGE"
EVENT_PARENT_JUDGE = "PARENT_JUDGE"
EVENT_RESOLUTION = "RESOLUTION"
EVENT_FOLD = "FOLD"

WINNER_SOURCE_RULE = "conservative-conjunction"
WINNER_SOURCE_LAST_WRITER = "last-writer-wins"

REMAINING_KIND_CHILD_INCOMPLETE = "child-incomplete"


class UnboundedChildError(ValueError):
    """The child artifact is not an answer to the bounded question it was spawned for."""


class NestedSpecError(ValueError):
    """The nested run cannot be set up as specified (bad question, order, artifact...)."""


# --------------------------------------------------------------------------- kernel


class InMemoryKernel:
    """Local event log: every event the topology produces is recorded here and nowhere else."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(self, event: Mapping[str, Any]) -> dict[str, Any]:
        rec = {"seq": len(self.events) + 1, **dict(event)}
        self.events.append(rec)
        return rec


def reducer_invocations(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The ``CHILD_BOUNDARY_JUDGE`` events in ``events``, in recording order."""
    return [dict(e) for e in events if e.get("kind") == EVENT_CHILD_BOUNDARY_JUDGE]


# --------------------------------------------------------------------------- typed inputs


@dataclass(frozen=True)
class BoundedQuestion:
    """The one question a subcouncil may be spawned for, with a hard round budget."""

    question_id: str
    prompt: str
    max_rounds: int = 1

    def __post_init__(self) -> None:
        if not str(self.question_id or "").strip():
            raise NestedSpecError("a bounded question needs a non-empty question_id")
        if (
            not isinstance(self.max_rounds, int)
            or isinstance(self.max_rounds, bool)
            or self.max_rounds < 1
        ):
            raise NestedSpecError(
                f"max_rounds must be a positive int, got {self.max_rounds!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "prompt": self.prompt,
            "max_rounds": self.max_rounds,
        }


# --------------------------------------------------------------------------- typed outputs


@dataclass(frozen=True)
class SpawnResult:
    """A spawned child: the bound it ran under, its artifact, and its boundary verdict."""

    question: BoundedQuestion
    child: dict[str, Any]
    child_verdict: CompletionVerdict
    rounds: int

    @property
    def child_id(self) -> str:
        return self.child_verdict.artifact_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question.to_dict(),
            "child_id": self.child_id,
            "rounds": self.rounds,
            "child_verdict": self.child_verdict.to_dict(),
        }


@dataclass(frozen=True)
class Resolution:
    """How a parent/child completion pair was folded, and by what rule."""

    parent: CompletionVerdict
    child: CompletionVerdict
    agreed: bool
    winner_complete: bool
    rule_id: str | None
    incidental: bool
    blocking_party: str | None
    order: tuple[str, ...]
    winner_source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "incidental": self.incidental,
            "agreed": self.agreed,
            "winner_complete": self.winner_complete,
            "blocking_party": self.blocking_party,
            "order": list(self.order),
            "winner_source": self.winner_source,
            "parent_complete": self.parent.complete,
            "parent_reason": self.parent.reason,
            "child_complete": self.child.complete,
            "child_reason": self.child.reason,
            "child_id": self.child.artifact_id,
            "parent_id": self.parent.artifact_id,
        }


@dataclass
class NestedResult:
    """Output of ``run_nested``: the spawn, the resolution, the folded parent, the events."""

    spawn: SpawnResult
    resolution: Resolution
    parent: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spawn": self.spawn.to_dict(),
            "resolution": self.resolution.to_dict(),
            "parent": dict(self.parent),
            "events": [dict(e) for e in self.events],
        }


# --------------------------------------------------------------------------- helpers


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, Mapping)):
        return [value]
    try:
        return list(value)
    except TypeError:
        return [value]


def _artifact_id(artifact: Mapping[str, Any]) -> str:
    return str(artifact.get("id") or artifact.get("council_id") or "<anonymous>")


def _rounds_of(artifact: Mapping[str, Any]) -> int:
    raw = artifact.get("rounds", 1)
    if isinstance(raw, bool) or not isinstance(raw, int):
        try:
            raw = int(raw)
        except (TypeError, ValueError):
            raise UnboundedChildError(
                f"child {_artifact_id(artifact)!r} reports unreadable rounds={raw!r}"
            ) from None
    return raw


def _normalise_order(order: Sequence[str] | None) -> tuple[str, ...]:
    if order is None:
        return DEFAULT_ORDER
    parties = tuple(str(p) for p in order)
    if sorted(parties) != sorted(PARTIES):
        raise NestedSpecError(
            f"order must be a permutation of {list(PARTIES)}, got {list(parties)}"
        )
    return parties


def check_bounded(question: BoundedQuestion, artifact: Mapping[str, Any]) -> int:
    """Refuse a child that is not an answer to ``question`` within its round budget.

    Returns the number of rounds the child ran. Raises ``UnboundedChildError`` when the
    child's ``question_id`` differs from the bound, or it ran more rounds than allowed.
    """
    if not isinstance(question, BoundedQuestion):
        raise NestedSpecError(
            f"spawn needs a BoundedQuestion, got {type(question).__name__}"
        )
    if not isinstance(artifact, Mapping):
        raise NestedSpecError(
            f"child artifact must be a mapping, got {type(artifact).__name__}"
        )
    child_q = artifact.get("question_id")
    if child_q != question.question_id:
        raise UnboundedChildError(
            f"child {_artifact_id(artifact)!r} answers {child_q!r}, "
            f"not the bounded question {question.question_id!r}"
        )
    rounds = _rounds_of(artifact)
    if rounds < 0 or rounds > question.max_rounds:
        raise UnboundedChildError(
            f"child {_artifact_id(artifact)!r} ran {rounds} rounds; "
            f"bound is max_rounds={question.max_rounds}"
        )
    return rounds


# --------------------------------------------------------------------------- reducer seam


def _judge_at_child_boundary(artifact: Mapping[str, Any]) -> CompletionVerdict:
    """The ONLY way a child's completion is decided: the shared reducer, at this locus."""
    return shared_judge(artifact, locus="child-boundary")


def _judge_parent_after_fold(artifact: Mapping[str, Any]) -> CompletionVerdict:
    """The parent's own completion, decided by the same shared reducer."""
    return shared_judge(artifact, locus="parent-after-fold")


def _verdict_event(kind: str, verdict: CompletionVerdict) -> dict[str, Any]:
    return {
        "kind": kind,
        "locus": verdict.locus,
        "reducer": verdict.reducer,
        "reducer_path": REDUCER_PATH,
        "artifact_id": verdict.artifact_id,
        "complete": verdict.complete,
        "reason": verdict.reason,
        "self_report_complete": verdict.self_report_complete,
        "self_report_disagrees": verdict.self_report_disagrees,
        "delegated": verdict.delegated,
    }


# --------------------------------------------------------------------------- spawn


def spawn_subcouncil(
    *,
    parent: Mapping[str, Any],
    question: BoundedQuestion,
    child_artifact: Mapping[str, Any],
    kernel: InMemoryKernel | None = None,
) -> SpawnResult:
    """Spawn a child for ``question``, record its turns, judge it at the child boundary."""
    if not isinstance(parent, Mapping):
        raise NestedSpecError(f"parent must be a mapping, got {type(parent).__name__}")
    rounds = check_bounded(question, child_artifact)
    log = kernel if kernel is not None else InMemoryKernel()
    child = dict(child_artifact)
    child_id = _artifact_id(child)
    parent_id = _artifact_id(parent)
    log.record(
        {
            "kind": EVENT_SPAWN,
            "parent_id": parent_id,
            "child_id": child_id,
            "question_id": question.question_id,
            "max_rounds": question.max_rounds,
            "rounds": rounds,
        }
    )
    participant = str(child.get("participant_id") or child_id)
    for turn in range(1, rounds + 1):
        log.record(
            {
                "kind": EVENT_TURN,
                "child_id": child_id,
                "participant_id": participant,
                "question_id": question.question_id,
                "round": turn,
                "of_max_rounds": question.max_rounds,
            }
        )
    verdict = _judge_at_child_boundary(child)
    log.record(_verdict_event(EVENT_CHILD_BOUNDARY_JUDGE, verdict))
    return SpawnResult(question=question, child=child, child_verdict=verdict, rounds=rounds)


# --------------------------------------------------------------------------- resolution


def resolve_disagreement(
    parent_verdict: CompletionVerdict,
    child_verdict: CompletionVerdict,
    *,
    apply_resolution_rule: bool = True,
    order: Sequence[str] | None = None,
) -> Resolution:
    """Fold two completion verdicts into one by the named rule (or, as the control, not).

    Rule ON (``RESOLUTION_RULE_ID``): COMPLETE iff both verdicts are COMPLETE; the
    incomplete side is the ``blocking_party`` (``"both"`` when neither is complete).
    Rule OFF: last-writer-wins over ``order`` -- whichever party is processed last sets
    the winner. The result is labelled ``incidental`` and carries no rule id.
    """
    parties = _normalise_order(order)
    by_party = {PARTY_PARENT: parent_verdict, PARTY_CHILD: child_verdict}
    agreed = bool(parent_verdict.complete) == bool(child_verdict.complete)

    if apply_resolution_rule:
        winner = bool(parent_verdict.complete) and bool(child_verdict.complete)
        blockers = [p for p in (PARTY_CHILD, PARTY_PARENT) if not by_party[p].complete]
        if not blockers:
            blocking: str | None = None
        elif len(blockers) == 1:
            blocking = blockers[0]
        else:
            blocking = PARTY_BOTH
        return Resolution(
            parent=parent_verdict,
            child=child_verdict,
            agreed=agreed,
            winner_complete=winner,
            rule_id=RESOLUTION_RULE_ID,
            incidental=False,
            blocking_party=blocking,
            order=parties,
            winner_source=WINNER_SOURCE_RULE,
        )

    last = parties[-1]
    winner = bool(by_party[last].complete)
    return Resolution(
        parent=parent_verdict,
        child=child_verdict,
        agreed=agreed,
        winner_complete=winner,
        rule_id=None,
        incidental=True,
        blocking_party=None,
        order=parties,
        winner_source=f"{WINNER_SOURCE_LAST_WRITER}:{last}",
    )


def uses_self_report_as_winner(result: NestedResult) -> bool:
    """Detector: did the folded completion follow the child's self-report bit?

    True when the child's own bit contradicts the reducer and the fold sided with the
    bit -- the failure the shared reducer exists to make impossible. A fold whose child
    bit agrees with the reducer gives no signal either way and returns False.
    """
    verdict = result.spawn.child_verdict
    if verdict.self_report_complete is None or not verdict.self_report_disagrees:
        return False
    return bool(result.resolution.winner_complete) == bool(verdict.self_report_complete)


# --------------------------------------------------------------------------- fold


def fold_child_into_parent(
    parent: Mapping[str, Any], spawn: SpawnResult, resolution: Resolution
) -> dict[str, Any]:
    """Build the parent artifact after the fold. The parent's own fields are kept.

    Added: ``completion`` (the resolved bool), ``resolution``, ``children``, the child's
    dissent and minority report appended verbatim to ``dissent``, ``child_evidence_cited``
    (the child's evidence, cited whenever the parent's fold overrules the child's own
    claim), and -- when the child is reducer-INCOMPLETE -- a ``remaining_work`` item naming
    the child so any outer boundary that judges this artifact sees the block.
    """
    folded = dict(parent)
    child = spawn.child
    child_id = spawn.child_id

    dissent = [d for d in _as_list(folded.get("dissent")) if d not in (None, "")]
    for entry in _as_list(child.get("dissent")):
        if entry in (None, ""):
            continue
        row = dict(entry) if isinstance(entry, Mapping) else {"text": str(entry)}
        row.setdefault("source_council_id", child_id)
        dissent.append(row)
    minority = child.get("minority_report")
    if isinstance(minority, Mapping) and minority:
        row = dict(minority)
        row.setdefault("source_council_id", child_id)
        row.setdefault("kind", "minority-report")
        dissent.append(row)
    elif isinstance(minority, str) and minority.strip():
        dissent.append(
            {"id": f"mr-{child_id}", "text": minority, "source_council_id": child_id,
             "kind": "minority-report"}
        )
    folded["dissent"] = dissent

    child_evidence = [e for e in _as_list(child.get("evidence")) if e not in (None, "")]
    folded["child_evidence_cited"] = list(child_evidence)

    remaining = [r for r in _as_list(folded.get("remaining_work")) if r not in (None, "")]
    if not spawn.child_verdict.complete:
        remaining.append(
            {
                "id": f"child-incomplete:{child_id}",
                "kind": REMAINING_KIND_CHILD_INCOMPLETE,
                "child_id": child_id,
                "question_id": spawn.question.question_id,
                "reason": spawn.child_verdict.reason,
                "locus": spawn.child_verdict.locus,
            }
        )
    folded["remaining_work"] = remaining

    children = list(_as_list(folded.get("children")))
    children.append(
        {
            "child_id": child_id,
            "question_id": spawn.question.question_id,
            "rounds": spawn.rounds,
            "complete": spawn.child_verdict.complete,
            "reason": spawn.child_verdict.reason,
            "reducer": spawn.child_verdict.reducer,
            "self_report_complete": spawn.child_verdict.self_report_complete,
        }
    )
    folded["children"] = children
    folded["completion"] = bool(resolution.winner_complete)
    folded["resolution"] = resolution.to_dict()
    folded["reducer_module"] = REDUCER_MODULE
    folded["reducer_path"] = REDUCER_PATH
    return folded


# --------------------------------------------------------------------------- runs


def run_nested(
    *,
    parent: Mapping[str, Any],
    question: BoundedQuestion,
    child_artifact: Mapping[str, Any],
    kernel: InMemoryKernel | None = None,
    apply_resolution_rule: bool = True,
    order: Sequence[str] | None = None,
) -> NestedResult:
    """Spawn the child, judge both sides with the shared reducer, resolve, fold."""
    log = kernel if kernel is not None else InMemoryKernel()
    parties = _normalise_order(order)

    spawn: SpawnResult | None = None
    parent_verdict: CompletionVerdict | None = None
    for party in parties:
        if party == PARTY_CHILD:
            spawn = spawn_subcouncil(
                parent=parent, question=question, child_artifact=child_artifact, kernel=log
            )
        else:
            parent_verdict = _judge_parent_after_fold(parent)
            log.record(_verdict_event(EVENT_PARENT_JUDGE, parent_verdict))
    assert spawn is not None and parent_verdict is not None  # order is a permutation

    resolution = resolve_disagreement(
        parent_verdict,
        spawn.child_verdict,
        apply_resolution_rule=apply_resolution_rule,
        order=parties,
    )
    log.record({"kind": EVENT_RESOLUTION, **resolution.to_dict()})
    folded = fold_child_into_parent(parent, spawn, resolution)
    log.record(
        {
            "kind": EVENT_FOLD,
            "parent_id": _artifact_id(parent),
            "child_id": spawn.child_id,
            "completion": folded["completion"],
            "dissent_ids": [
                d.get("id") for d in folded["dissent"] if isinstance(d, Mapping)
            ],
            "remaining_count": len(folded["remaining_work"]),
        }
    )
    return NestedResult(spawn=spawn, resolution=resolution, parent=folded, events=log.events)


def run_depth2(
    *,
    grandparent: Mapping[str, Any],
    mid: Mapping[str, Any],
    leaf: Mapping[str, Any],
    mid_question: BoundedQuestion,
    leaf_question: BoundedQuestion,
    kernel: InMemoryKernel | None = None,
    apply_resolution_rule: bool = True,
    order: Sequence[str] | None = None,
) -> dict[str, NestedResult]:
    """Two levels: the leaf folds into mid, then the *folded* mid folds into grandparent.

    A blocked leaf leaves ``remaining_work`` on the folded mid, so the outer child-boundary
    judge (the same shared reducer) sees the block and the grandparent cannot complete.
    """
    log = kernel if kernel is not None else InMemoryKernel()
    inner = run_nested(
        parent=mid,
        question=leaf_question,
        child_artifact=leaf,
        kernel=log,
        apply_resolution_rule=apply_resolution_rule,
        order=order,
    )
    outer = run_nested(
        parent=grandparent,
        question=mid_question,
        child_artifact=inner.parent,
        kernel=log,
        apply_resolution_rule=apply_resolution_rule,
        order=order,
    )
    return {"inner": inner, "outer": outer}


__all__ = [
    "DEFAULT_ORDER",
    "EVENT_CHILD_BOUNDARY_JUDGE",
    "EVENT_FOLD",
    "EVENT_PARENT_JUDGE",
    "EVENT_RESOLUTION",
    "EVENT_SPAWN",
    "EVENT_TURN",
    "LOCUS_CHILD_BOUNDARY",
    "LOCUS_PARENT_AFTER_FOLD",
    "PARTIES",
    "PARTY_BOTH",
    "PARTY_CHILD",
    "PARTY_PARENT",
    "RESOLUTION_RULE_ID",
    "SPEC_ANCHOR",
    "BoundedQuestion",
    "InMemoryKernel",
    "NestedResult",
    "NestedSpecError",
    "Resolution",
    "SpawnResult",
    "UnboundedChildError",
    "check_bounded",
    "fold_child_into_parent",
    "reducer_invocations",
    "resolve_disagreement",
    "run_depth2",
    "run_nested",
    "spawn_subcouncil",
    "uses_self_report_as_winner",
]
