"""Shared completion reducer for council topologies.

Nested councils (``topology.nested``), councils-of-councils (``topology.coc``) and
every other fan-in seam must ask *one* reducer whether a council artifact is
complete. The artifact's own ``self_report_complete`` bit is evidence about what
the council *claims*; it is never the verdict. Averaging a DONE sibling with a
NOT-DONE sibling into DONE is the _USER-PROMPTS.md:11343 failure class, and the
way to make it impossible is to have a single, named, importable predicate that
each boundary calls and each probe can re-call for an independent recount.

The reducer is an AND-gate over explicit conditions, mirroring the program-wide
oracle (``agentspec.oracle.judge``). When that oracle is importable and the
artifact carries a receipt path, the verdict is delegated to it; otherwise the
local gate below decides. Either way the result is a :class:`CompletionVerdict`
whose ``reducer`` names this module, so a fold that skipped the shared reducer
is visible in the trace it leaves behind.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

REDUCER_MODULE = "tools.council.shared_completion"
REDUCER_PATH = "tools/council/shared_completion.py"

COMPLETE_STATES = frozenset({"SUCCESS", "COMPLETE", "COMPLETED", "DONE", "DELIVERED"})
BLOCKING_STATES = frozenset(
    {
        "BLOCKED",
        "FAILED",
        "FAIL",
        "ABORTED",
        "SEVERED",
        "INCOMPLETE",
        "PARTIAL",
        "PENDING",
        "RUNNING",
        "TIMEOUT",
    }
)

# Condition ids, in evaluation order. The first failing one becomes the reason.
COND_STATE = "state-is-terminal-success"
COND_NOT_BLOCKED = "state-not-blocking"
COND_EVIDENCE = "evidence-cited"
COND_REMAINING = "no-remaining-work"
COND_DISSENT = "no-blocking-dissent"
CONDITIONS: tuple[str, ...] = (
    COND_STATE,
    COND_NOT_BLOCKED,
    COND_EVIDENCE,
    COND_REMAINING,
    COND_DISSENT,
)

REASON_COMPLETE = "all-conditions-passed"


class ArtifactError(TypeError):
    """Raised when the thing offered for judging is not a council artifact."""


@dataclass(frozen=True)
class Condition:
    """One clause of the AND-gate with the observation that decided it."""

    id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True)
class CompletionVerdict:
    """The reducer's answer for one artifact at one boundary."""

    complete: bool
    reason: str
    locus: str
    artifact_id: str
    conditions: tuple[Condition, ...] = field(default_factory=tuple)
    self_report_complete: bool | None = None
    reducer: str = REDUCER_MODULE
    delegated: bool = False

    @property
    def self_report_disagrees(self) -> bool:
        """True when the council's own bit contradicts the reducer."""
        if self.self_report_complete is None:
            return False
        return bool(self.self_report_complete) != self.complete

    @property
    def failed_conditions(self) -> tuple[str, ...]:
        return tuple(c.id for c in self.conditions if not c.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "complete": self.complete,
            "reason": self.reason,
            "locus": self.locus,
            "reducer": self.reducer,
            "delegated": self.delegated,
            "self_report_complete": self.self_report_complete,
            "self_report_disagrees": self.self_report_disagrees,
            "conditions": [c.to_dict() for c in self.conditions],
        }


def _state_of(artifact: Mapping[str, Any]) -> str:
    raw = artifact.get("state", artifact.get("status", ""))
    return str(raw or "").strip().upper()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Mapping):
        return [value]
    try:
        return list(value)
    except TypeError:
        return [value]


def _dissent_blocks(item: Any) -> bool:
    if not isinstance(item, Mapping):
        return False
    if item.get("blocking") is True:
        return True
    severity = str(item.get("severity", "")).strip().lower()
    return severity in {"blocking", "block", "veto"}


def evaluate_conditions(artifact: Mapping[str, Any]) -> tuple[Condition, ...]:
    """Evaluate every clause of the gate; never short-circuits, so a probe can
    see all of the reasons an artifact fell short rather than only the first."""
    state = _state_of(artifact)
    evidence = [e for e in _as_list(artifact.get("evidence")) if e not in (None, "")]
    remaining = [
        r
        for key in ("remaining_work", "open_items", "todo", "unfinished")
        for r in _as_list(artifact.get(key))
        if r not in (None, "")
    ]
    blocking_dissent = [
        d for d in _as_list(artifact.get("dissent")) if _dissent_blocks(d)
    ]

    return (
        Condition(
            COND_STATE,
            state in COMPLETE_STATES,
            f"state={state or '<missing>'} complete_states={sorted(COMPLETE_STATES)}",
        ),
        Condition(
            COND_NOT_BLOCKED,
            state not in BLOCKING_STATES,
            f"state={state or '<missing>'}",
        ),
        Condition(COND_EVIDENCE, len(evidence) > 0, f"evidence_count={len(evidence)}"),
        Condition(
            COND_REMAINING, len(remaining) == 0, f"remaining_count={len(remaining)}"
        ),
        Condition(
            COND_DISSENT,
            len(blocking_dissent) == 0,
            "blocking_dissent="
            + ",".join(str(d.get("id", "?")) for d in blocking_dissent),
        ),
    )


def _oracle_judge(artifact: Mapping[str, Any]) -> CompletionVerdict | None:
    """Delegate to ``agentspec.oracle`` when it is importable and the artifact
    names a receipt. Returns ``None`` when delegation is not possible so the
    caller falls back to the local gate (never to the self-report bit)."""
    receipt_path = artifact.get("receipt_path")
    if not receipt_path:
        return None
    try:
        from agentspec import oracle  # type: ignore[import-not-found]
    except Exception:
        try:
            from tools.agentspec.agentspec import oracle  # type: ignore[no-redef]
        except Exception:
            return None
    judge_path = getattr(oracle, "judge_receipt_path", None)
    if not callable(judge_path):
        return None
    try:
        verdict = judge_path(receipt_path)
    except Exception as exc:  # the oracle refusing is itself a NOT-COMPLETE verdict
        return CompletionVerdict(
            complete=False,
            reason=f"oracle-error:{type(exc).__name__}",
            locus="",
            artifact_id="",
            delegated=True,
        )
    ok = bool(getattr(verdict, "ok", False))
    reason = getattr(verdict, "reason", None) or (
        REASON_COMPLETE if ok else "oracle-not-ok"
    )
    passed = tuple(getattr(verdict, "passed_clauses", ()) or ())
    return CompletionVerdict(
        complete=ok,
        reason=str(reason),
        locus="",
        artifact_id="",
        conditions=tuple(Condition(str(c), True, "oracle-clause") for c in passed),
        delegated=True,
    )


def judge(
    artifact: Mapping[str, Any], *, locus: str = "unspecified"
) -> CompletionVerdict:
    """Decide whether ``artifact`` is complete at boundary ``locus``.

    ``self_report_complete`` is recorded but never consulted for the verdict.
    """
    if not isinstance(artifact, Mapping):
        raise ArtifactError(
            f"judge expects a council artifact mapping, got {type(artifact).__name__}"
        )
    artifact_id = str(artifact.get("id") or artifact.get("council_id") or "<anonymous>")
    raw_bit = artifact.get("self_report_complete")
    self_bit = None if raw_bit is None else bool(raw_bit)

    delegated = _oracle_judge(artifact)
    if delegated is not None:
        return CompletionVerdict(
            complete=delegated.complete,
            reason=delegated.reason,
            locus=str(locus),
            artifact_id=artifact_id,
            conditions=delegated.conditions,
            self_report_complete=self_bit,
            delegated=True,
        )

    conditions = evaluate_conditions(artifact)
    failed = [c for c in conditions if not c.passed]
    complete = not failed
    reason = REASON_COMPLETE if complete else f"{failed[0].id}:{failed[0].detail}"
    return CompletionVerdict(
        complete=complete,
        reason=reason,
        locus=str(locus),
        artifact_id=artifact_id,
        conditions=conditions,
        self_report_complete=self_bit,
    )


def judge_many(
    artifacts: Iterable[Mapping[str, Any]], *, locus: str = "unspecified"
) -> list[CompletionVerdict]:
    return [judge(a, locus=locus) for a in artifacts]


def conjunction(verdicts: Iterable[CompletionVerdict]) -> tuple[bool, str | None]:
    """Conservative fold: COMPLETE iff every verdict is complete. Returns the
    fold and the id of the first blocking artifact (``None`` when none blocks).
    Two verdicts never average; one NOT-DONE blocks the whole."""
    for v in verdicts:
        if not v.complete:
            return False, v.artifact_id
    return True, None


__all__ = [
    "REDUCER_MODULE",
    "REDUCER_PATH",
    "COMPLETE_STATES",
    "BLOCKING_STATES",
    "CONDITIONS",
    "REASON_COMPLETE",
    "ArtifactError",
    "Condition",
    "CompletionVerdict",
    "evaluate_conditions",
    "judge",
    "judge_many",
    "conjunction",
]
