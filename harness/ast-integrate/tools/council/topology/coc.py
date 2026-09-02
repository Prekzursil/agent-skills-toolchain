"""Council-of-councils topology: sibling subcouncils fan in to one parent.

Roles (TST-0285 / IMP-0288 follow-on; spec anchors ``_USER-PROMPTS.md:11343`` "nested
councils disagree on completion" and ``:10926`` "nested subcouncil, council-of-councils")
------------------------------------------------------------------------------------------
* ``fan_in`` -- N sibling artifacts, each spawned for its own ``BoundedQuestion``
  (``topology.nested`` supplies the bound check), are judged one by one at the sibling
  boundary by the shared completion reducer, then the parent is judged by the same
  reducer, and the verdicts are folded by the named fan-in rule.
* ``resolve_sibling_disagreement`` -- ``FANIN_RULE_ID``: conservative conjunction. The
  parent is COMPLETE iff every sibling is reducer-COMPLETE AND the parent itself is
  reducer-COMPLETE. Every incomplete party is named in ``blocking_parties``. The average
  and the majority of sibling verdicts are *computed and recorded* (``average``,
  ``majority_complete``) so a reader can see what averaging would have said, but neither
  is ever the winner. ``apply_resolution_rule=False`` is the negative control: the fold
  degrades to last-writer-wins over ``order``, labelled ``incidental`` with no rule id.
* ``run_depth2_siblings`` -- two mids each fold their own leaf (``nested.run_nested``), then
  the two folded mids fan in to the grandparent.

Dissent (A11)
-------------
Each sibling's dissent entries and minority report are copied onto the parent verbatim
and additionally recorded as ``a11.dissent-survival-trace.v1`` rows carrying the source
council id, so the survival of every minority id is checkable by walking the parent.

Verbatim inputs
---------------
The parent records every sibling's artifact together with the reducer's verdict on it in
``subcouncil_inputs_verbatim``; a probe can re-call ``shared_judge`` on each recorded
artifact for an independent recount.
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
from tools.council.topology import nested as N

SPEC_ANCHOR = (
    "_USER-PROMPTS.md:11343 nested councils disagree on completion; "
    ":10926 nested subcouncil, council-of-councils"
)
FANIN_RULE_ID = "coc.sibling-disagreement.conservative-conjunction.v1"
A11_KIND = "a11.dissent-survival-trace.v1"

LOCUS_SIBLING_BOUNDARY = "child-boundary"
LOCUS_PARENT_AFTER_FANIN = "parent-after-fanin"

EVENT_CHILD_BOUNDARY_JUDGE = N.EVENT_CHILD_BOUNDARY_JUDGE
EVENT_PARENT_JUDGE = N.EVENT_PARENT_JUDGE
EVENT_COC_FANIN = "COC_FANIN"

WINNER_SOURCE_RULE = "conservative-conjunction"
WINNER_SOURCE_LAST_WRITER = "last-writer-wins"

InMemoryKernel = N.InMemoryKernel
BoundedQuestion = N.BoundedQuestion
UnboundedChildError = N.UnboundedChildError


class FanInSpecError(ValueError):
    """The fan-in cannot be set up as specified (no siblings, mismatched questions, ...)."""


# --------------------------------------------------------------------------- typed outputs


@dataclass(frozen=True)
class SiblingRecord:
    """One sibling at the fan-in boundary: its artifact and the shared reducer's verdict."""

    council_id: str
    question: BoundedQuestion
    artifact: dict[str, Any]
    verdict: CompletionVerdict
    rounds: int

    @property
    def complete(self) -> bool:
        return bool(self.verdict.complete)

    @property
    def reason(self) -> str:
        return self.verdict.reason

    @property
    def self_report_complete(self) -> bool | None:
        return self.verdict.self_report_complete

    def verbatim_row(self) -> dict[str, Any]:
        return {
            "council_id": self.council_id,
            "question_id": self.question.question_id,
            "artifact": dict(self.artifact),
            "complete": self.complete,
            "reason": self.reason,
            "locus": self.verdict.locus,
            "reducer": self.verdict.reducer,
            "reducer_path": REDUCER_PATH,
            "self_report_complete": self.self_report_complete,
            "self_report_disagrees": self.verdict.self_report_disagrees,
        }


@dataclass(frozen=True)
class FanInResolution:
    """How the sibling verdicts and the parent verdict were folded, and by what rule."""

    parent: CompletionVerdict
    siblings: tuple[CompletionVerdict, ...]
    agreed: bool
    winner_complete: bool
    rule_id: str | None
    incidental: bool
    blocking_parties: tuple[str, ...]
    majority_complete: bool
    average: float | None
    order: tuple[str, ...]
    winner_source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "incidental": self.incidental,
            "agreed": self.agreed,
            "winner_complete": self.winner_complete,
            "blocking_parties": list(self.blocking_parties),
            "rejected_aggregations": {
                "majority_complete": self.majority_complete,
                "average": self.average,
            },
            "order": list(self.order),
            "winner_source": self.winner_source,
            "parent_id": self.parent.artifact_id,
            "parent_complete": self.parent.complete,
            "parent_reason": self.parent.reason,
            "siblings": [
                {"council_id": v.artifact_id, "complete": v.complete, "reason": v.reason}
                for v in self.siblings
            ],
        }


@dataclass
class FanInResult:
    """Output of ``fan_in``: sibling records, the resolution, the folded parent, events."""

    siblings: list[SiblingRecord]
    resolution: FanInResolution
    parent: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "siblings": [s.verbatim_row() for s in self.siblings],
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


def _normalise_order(
    order: Sequence[str] | None, council_ids: Sequence[str]
) -> tuple[str, ...]:
    ids = tuple(council_ids)
    if order is None:
        return ids
    parties = tuple(str(p) for p in order)
    if sorted(parties) != sorted(ids):
        raise FanInSpecError(
            f"order must be a permutation of the sibling ids {list(ids)}, got {list(parties)}"
        )
    return parties


# --------------------------------------------------------------------------- reducer seam


def _judge_sibling_boundary(artifact: Mapping[str, Any]) -> CompletionVerdict:
    """The ONLY way a sibling's completion is decided: the shared reducer, at this locus."""
    return shared_judge(artifact, locus="child-boundary")


def _judge_parent_after_fanin(artifact: Mapping[str, Any]) -> CompletionVerdict:
    """The parent's own completion, decided by the same shared reducer."""
    return shared_judge(artifact, locus="parent-after-fanin")


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


# --------------------------------------------------------------------------- resolution


def resolve_sibling_disagreement(
    parent_verdict: CompletionVerdict,
    sibling_verdicts: Sequence[CompletionVerdict],
    *,
    apply_resolution_rule: bool = True,
    order: Sequence[str] | None = None,
) -> FanInResolution:
    """Fold the sibling verdicts and the parent verdict by the named rule (or not).

    Rule ON (``FANIN_RULE_ID``): COMPLETE iff every sibling AND the parent are COMPLETE;
    every incomplete party is a blocking party. The sibling average and majority are
    recorded as rejected aggregations, never as the winner.
    Rule OFF: last-writer-wins -- the last sibling in ``order`` sets the winner; the
    result is ``incidental`` with no rule id.
    """
    verdicts = tuple(sibling_verdicts)
    if not verdicts:
        raise FanInSpecError("fan-in needs at least one sibling verdict")
    ids = [v.artifact_id for v in verdicts]
    parties = _normalise_order(order, ids)
    completes = [bool(v.complete) for v in verdicts]
    n = len(completes)
    n_complete = sum(1 for c in completes if c)
    average = n_complete / n
    majority = n_complete > n / 2
    agreed = len({*completes, bool(parent_verdict.complete)}) == 1

    if apply_resolution_rule:
        winner = bool(parent_verdict.complete) and all(completes)
        blocking = [v.artifact_id for v in verdicts if not v.complete]
        if not parent_verdict.complete:
            blocking.append(parent_verdict.artifact_id)
        return FanInResolution(
            parent=parent_verdict,
            siblings=verdicts,
            agreed=agreed,
            winner_complete=winner,
            rule_id=FANIN_RULE_ID,
            incidental=False,
            blocking_parties=tuple(blocking),
            majority_complete=majority,
            average=average,
            order=parties,
            winner_source=WINNER_SOURCE_RULE,
        )

    by_id = {v.artifact_id: v for v in verdicts}
    last = parties[-1]
    return FanInResolution(
        parent=parent_verdict,
        siblings=verdicts,
        agreed=agreed,
        winner_complete=bool(by_id[last].complete),
        rule_id=None,
        incidental=True,
        blocking_parties=(),
        majority_complete=majority,
        average=average,
        order=parties,
        winner_source=f"{WINNER_SOURCE_LAST_WRITER}:{last}",
    )


# --------------------------------------------------------------------------- A11 trace


def _a11(record: SiblingRecord) -> list[dict[str, Any]]:
    """A11 dissent-survival rows for one sibling: each dissent entry and the minority report."""
    rows: list[dict[str, Any]] = []
    artifact = record.artifact

    def row(payload: Mapping[str, Any], kind: str) -> dict[str, Any]:
        return {
            "kind": A11_KIND,
            "id": payload.get("id"),
            "dissent_kind": kind,
            "source_council_id": record.council_id,
            "source_question_id": record.question.question_id,
            "source_complete": record.complete,
            "payload": dict(payload),
        }

    for entry in _as_list(artifact.get("dissent")):
        if entry in (None, ""):
            continue
        payload = dict(entry) if isinstance(entry, Mapping) else {"text": str(entry)}
        rows.append(row(payload, "dissent"))
    minority = artifact.get("minority_report")
    if isinstance(minority, Mapping) and minority:
        rows.append(row(dict(minority), "minority-report"))
    elif isinstance(minority, str) and minority.strip():
        rows.append(row({"id": f"mr-{record.council_id}", "text": minority}, "minority-report"))
    return rows


# --------------------------------------------------------------------------- fold


def fold_siblings_into_parent(
    parent: Mapping[str, Any],
    records: Sequence[SiblingRecord],
    resolution: FanInResolution,
) -> dict[str, Any]:
    """Build the parent artifact after fan-in. The parent's own fields are kept.

    Added: ``completion`` (bool, the resolved winner -- never a midpoint), ``resolution``,
    ``subcouncil_inputs_verbatim`` (every sibling artifact with its reducer verdict),
    ``a11_dissent_trace`` rows, each sibling's dissent and minority report appended to
    ``dissent``, ``child_evidence_cited``, and a ``remaining_work`` item per incomplete
    sibling so an outer boundary judging this artifact sees the block.
    """
    folded = dict(parent)
    dissent = [d for d in _as_list(folded.get("dissent")) if d not in (None, "")]
    a11_rows: list[dict[str, Any]] = []
    evidence_cited: list[Any] = []
    remaining = [r for r in _as_list(folded.get("remaining_work")) if r not in (None, "")]
    children: list[dict[str, Any]] = list(_as_list(folded.get("children")))

    for record in records:
        rows = _a11(record)
        a11_rows.extend(rows)
        for r in rows:
            entry = dict(r["payload"])
            entry.setdefault("source_council_id", record.council_id)
            entry.setdefault("kind", r["dissent_kind"])
            dissent.append(entry)
        evidence_cited.extend(
            e for e in _as_list(record.artifact.get("evidence")) if e not in (None, "")
        )
        if not record.complete:
            remaining.append(
                {
                    "id": f"sibling-incomplete:{record.council_id}",
                    "kind": "sibling-incomplete",
                    "council_id": record.council_id,
                    "question_id": record.question.question_id,
                    "reason": record.reason,
                    "locus": record.verdict.locus,
                }
            )
        children.append(
            {
                "council_id": record.council_id,
                "question_id": record.question.question_id,
                "rounds": record.rounds,
                "complete": record.complete,
                "reason": record.reason,
                "reducer": record.verdict.reducer,
                "self_report_complete": record.self_report_complete,
            }
        )

    folded["dissent"] = dissent
    folded["a11_dissent_trace"] = a11_rows
    folded["child_evidence_cited"] = evidence_cited
    folded["remaining_work"] = remaining
    folded["children"] = children
    folded["subcouncil_inputs_verbatim"] = [r.verbatim_row() for r in records]
    folded["completion"] = bool(resolution.winner_complete)
    folded["resolution"] = resolution.to_dict()
    folded["reducer_module"] = REDUCER_MODULE
    folded["reducer_path"] = REDUCER_PATH
    folded["fanin_rule_id"] = resolution.rule_id
    return folded


# --------------------------------------------------------------------------- runs


def fan_in(
    *,
    parent: Mapping[str, Any],
    siblings: Sequence[Mapping[str, Any]],
    questions: Sequence[BoundedQuestion],
    kernel: InMemoryKernel | None = None,
    apply_resolution_rule: bool = True,
    order: Sequence[str] | None = None,
) -> FanInResult:
    """Judge every sibling at its boundary, judge the parent, resolve, fold.

    ``siblings[i]`` must be the answer to ``questions[i]`` (``UnboundedChildError``
    otherwise). ``order`` lists sibling council ids in processing order; it only changes
    the outcome when the rule is off.
    """
    if not isinstance(parent, Mapping):
        raise FanInSpecError(f"parent must be a mapping, got {type(parent).__name__}")
    if not siblings:
        raise FanInSpecError("fan-in needs at least one sibling")
    if len(siblings) != len(questions):
        raise FanInSpecError(
            f"{len(siblings)} siblings but {len(questions)} questions; one bound per sibling"
        )
    log = kernel if kernel is not None else InMemoryKernel()

    pending: dict[str, tuple[Mapping[str, Any], BoundedQuestion]] = {}
    ids: list[str] = []
    for artifact, question in zip(siblings, questions):
        cid = _artifact_id(artifact)
        if cid in pending:
            raise FanInSpecError(f"duplicate sibling council id {cid!r}")
        pending[cid] = (artifact, question)
        ids.append(cid)
    parties = _normalise_order(order, ids)

    records: list[SiblingRecord] = []
    for cid in parties:
        artifact, question = pending[cid]
        rounds = N.check_bounded(question, artifact)
        verdict = _judge_sibling_boundary(artifact)
        log.record(_verdict_event(EVENT_CHILD_BOUNDARY_JUDGE, verdict))
        records.append(
            SiblingRecord(
                council_id=cid,
                question=question,
                artifact=dict(artifact),
                verdict=verdict,
                rounds=rounds,
            )
        )
    by_id = {r.council_id: r for r in records}
    ordered = [by_id[cid] for cid in ids]  # caller's order for reporting

    parent_verdict = _judge_parent_after_fanin(parent)
    log.record(_verdict_event(EVENT_PARENT_JUDGE, parent_verdict))

    resolution = resolve_sibling_disagreement(
        parent_verdict,
        [r.verdict for r in ordered],
        apply_resolution_rule=apply_resolution_rule,
        order=parties,
    )
    folded = fold_siblings_into_parent(parent, ordered, resolution)
    log.record(
        {
            "kind": EVENT_COC_FANIN,
            "parent_id": _artifact_id(parent),
            "sibling_ids": list(ids),
            "order": list(parties),
            "completion": folded["completion"],
            "rule_id": resolution.rule_id,
            "incidental": resolution.incidental,
            "blocking_parties": list(resolution.blocking_parties),
            "a11_ids": [r.get("id") for r in folded["a11_dissent_trace"]],
        }
    )
    return FanInResult(siblings=ordered, resolution=resolution, parent=folded, events=log.events)


def run_depth2_siblings(
    *,
    grandparent: Mapping[str, Any],
    mid_done: Mapping[str, Any],
    mid_blocked: Mapping[str, Any],
    leaf_done: Mapping[str, Any],
    leaf_blocked: Mapping[str, Any],
    mid_done_question: BoundedQuestion,
    mid_blocked_question: BoundedQuestion,
    leaf_question: BoundedQuestion,
    kernel: InMemoryKernel | None = None,
    apply_resolution_rule: bool = True,
) -> dict[str, Any]:
    """Two mids each fold their own leaf, then the folded mids fan in to the grandparent."""
    log = kernel if kernel is not None else InMemoryKernel()
    inner_done = N.run_nested(
        parent=mid_done,
        question=leaf_question,
        child_artifact=leaf_done,
        kernel=log,
        apply_resolution_rule=apply_resolution_rule,
    )
    inner_blocked = N.run_nested(
        parent=mid_blocked,
        question=leaf_question,
        child_artifact=leaf_blocked,
        kernel=log,
        apply_resolution_rule=apply_resolution_rule,
    )
    outer = fan_in(
        parent=grandparent,
        siblings=[inner_done.parent, inner_blocked.parent],
        questions=[mid_done_question, mid_blocked_question],
        kernel=log,
        apply_resolution_rule=apply_resolution_rule,
    )
    return {"inner_done": inner_done, "inner_blocked": inner_blocked, "outer": outer}


__all__ = [
    "A11_KIND",
    "EVENT_CHILD_BOUNDARY_JUDGE",
    "EVENT_COC_FANIN",
    "EVENT_PARENT_JUDGE",
    "FANIN_RULE_ID",
    "LOCUS_PARENT_AFTER_FANIN",
    "LOCUS_SIBLING_BOUNDARY",
    "SPEC_ANCHOR",
    "BoundedQuestion",
    "FanInResolution",
    "FanInResult",
    "FanInSpecError",
    "InMemoryKernel",
    "SiblingRecord",
    "UnboundedChildError",
    "fan_in",
    "fold_siblings_into_parent",
    "resolve_sibling_disagreement",
    "run_depth2_siblings",
]
