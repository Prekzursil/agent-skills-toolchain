"""The HERMETIC eval registry — a parametrised set of executable rows, not a checklist.

A markdown checklist cannot be a gate. Each row here is a callable with a stated MEASURED
failure and a stated RED condition, runs against an in-process fake rail with an injected clock,
and projects its outcome onto the shared observation envelope.

Rows are addressed by id and the catalogue is passed in, so a caller (or a test) can add a
live-rail row without editing this module. Live rows are EXCLUDED by default:
``run_all()`` is hermetic, ``run_all(include_live=True)`` is opt-in, and pytest additionally
deselects ``live``-marked tests via :mod:`agentspec.evals.pytest_live`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from agentspec.envelope import ErrorDetail, Observation, error, success, warning
from agentspec.evals.impl import DEFAULT_IMPL, Impl
from agentspec.evals.rows import (
    r1_no_background_on_an_awaited_dispatch,
    r2_exit_zero_without_a_usable_receipt_is_severed,
    r3_a_progress_payload_is_never_a_result,
    r4_a_large_prompt_is_routed_off_argv,
    r5_hardening_is_required_and_win_arg_limit_retries_once,
    r6_no_dispatch_without_an_explicit_timeout,
    r8_the_dispatch_path_is_deterministic,
)


@dataclass(frozen=True, slots=True)
class EvalRow:
    """One eval. ``measured_failure`` and ``red_condition`` are mandatory prose, asserted
    non-trivial by ``tests/test_registry.py`` — a row without them is a checklist item."""

    id: str
    kind: str
    title: str
    measured_failure: str
    red_condition: str
    run: Callable[[Impl], tuple[bool, str]]
    live: bool = False


@dataclass(frozen=True, slots=True)
class EvalOutcome:
    """One row's result plus its observation envelope."""

    row_id: str
    passed: bool
    detail: str
    observation: Observation


REGISTRY: tuple[EvalRow, ...] = (
    EvalRow(
        id="R1",
        kind="regression",
        title="no fire-and-forget on a barrier-awaited dispatch",
        measured_failure=(
            "three Codex-backed subagents produced zero artifacts: each returned a "
            "'started in the background as task-...' receipt, and the real work then completed "
            "on disk and was discarded unread, because a backgrounded job's result is "
            "unreachable to the barrier waiting on it"
        ),
        red_condition=(
            "the rail launches, or the policy predicate accepts, a dispatch with "
            "background=True while awaited=True; or the guard over-reaches and also refuses an "
            "UNAWAITED background dispatch"
        ),
        run=r1_no_background_on_an_awaited_dispatch,
    ),
    EvalRow(
        id="R2",
        kind="regression",
        title="exit 0 without a usable receipt is SEVERED, never SUCCESS",
        measured_failure=(
            "a foreground dispatch returned after 6m59s carrying only a progress prefix and the "
            "caller forwarded that as its terminal result, while its own job record still read "
            "status=running"
        ),
        red_condition=(
            "any of {missing, empty, whitespace-only, unparseable, schema-invalid} receipts "
            "reports ok=True, loses severed=True, or renders a terminal line without "
            "'severed-stream'; or a fully good run stops reporting SUCCESS"
        ),
        run=r2_exit_zero_without_a_usable_receipt_is_severed,
    ),
    EvalRow(
        id="R3",
        kind="regression",
        title="a progress/background-job payload is never returned as a result",
        measured_failure=(
            "an agent's ENTIRE final answer was a background-job receipt, and another forwarded "
            "a raw '[codex] ...' progress stream as its terminal result"
        ),
        red_condition=(
            "any declared background phrase, or a payload of only bracketed progress lines, "
            "classifies as a result; or a real answer is misclassified as progress"
        ),
        run=r3_a_progress_payload_is_never_a_result,
    ),
    EvalRow(
        id="R4",
        kind="regression",
        title="a 40 KB prompt is routed by file/stdin and argv stays under the Windows cap",
        measured_failure=(
            "an inline prompt produced payload_len=34472 and killed the run with Windows "
            "os error 206; the CreateProcess cap is 32,767 chars, measured via libuv at "
            "32,745 OK -> 32,774 ENAMETOOLONG"
        ),
        red_condition=(
            "a 40 KB prompt reaches argv, the rendered command line reaches the cap, an "
            "over-cap command line is accepted, or the over-cap failure is not win-arg-limit"
        ),
        run=r4_a_large_prompt_is_routed_off_argv,
    ),
    EvalRow(
        id="R5",
        kind="regression",
        title="hardening flags are mandatory, and win-arg-limit retries exactly once",
        measured_failure=(
            "the active MCP inventory is what blows the argv limit, so omitting "
            "--ignore-user-config on a non-interactive codex call was the #1 execution blocker; "
            "and an unbounded retry on the same failure is a grind, not a recovery"
        ),
        red_condition=(
            "build_for_rail omits or stops verifying a declared hardening flag, win-arg-limit "
            "retries a second time, or an unrelated reason becomes retryable"
        ),
        run=r5_hardening_is_required_and_win_arg_limit_retries_once,
    ),
    EvalRow(
        id="R6",
        kind="regression",
        title="no dispatch without an explicit timeout",
        measured_failure=(
            "a silent default timeout is what a caller rationalised --background to escape, so "
            "an unbounded dispatch is how a hung unit becomes an invisible one"
        ),
        red_condition=(
            "the rail launches, or the policy predicate accepts, timeout_s=None or a "
            "non-positive timeout; or an explicit positive timeout is refused"
        ),
        run=r6_no_dispatch_without_an_explicit_timeout,
    ),
    EvalRow(
        id="R8",
        kind="regression",
        title="the dispatch path is deterministic: two runs, identical artifacts",
        measured_failure=(
            "a wall-clock or entropy read on the dispatch path makes two runs of one spec "
            "produce different artifacts, so no diff of them can mean anything"
        ),
        red_condition=(
            "the determinism static check stays silent on a known-broken fixture, a forbidden "
            "call appears on the dispatch path, or two identical scripted runs serialise "
            "differently"
        ),
        run=r8_the_dispatch_path_is_deterministic,
    ),
)


def rows(
    *, catalog: Sequence[EvalRow] = REGISTRY, include_live: bool = False
) -> tuple[EvalRow, ...]:
    """The rows to run. Live rows are dropped unless explicitly asked for."""
    return tuple(row for row in catalog if include_live or not row.live)


def row_ids(
    *, catalog: Sequence[EvalRow] = REGISTRY, include_live: bool = False
) -> tuple[str, ...]:
    """The ids of the rows :func:`rows` would run, in declaration order."""
    return tuple(row.id for row in rows(catalog=catalog, include_live=include_live))


def run_row(row: EvalRow, *, impl: Impl = DEFAULT_IMPL) -> EvalOutcome:
    """Run one row. A raising row is a FAILED outcome, never a propagated exception —
    an eval harness must always reach a terminal state."""
    try:
        passed, detail = row.run(impl)
    except Exception as exc:  # noqa: BLE001 -- a row must never take the harness down
        passed, detail = False, f"row raised {type(exc).__name__}: {exc}"
    return EvalOutcome(
        row_id=row.id,
        passed=passed,
        detail=detail,
        observation=_observe(row, passed=passed, detail=detail),
    )


def run_all(
    *,
    catalog: Sequence[EvalRow] = REGISTRY,
    impl: Impl = DEFAULT_IMPL,
    include_live: bool = False,
) -> tuple[EvalOutcome, ...]:
    """Run every selected row in declaration order."""
    return tuple(
        run_row(row, impl=impl)
        for row in rows(catalog=catalog, include_live=include_live)
    )


def summary(outcomes: Sequence[EvalOutcome]) -> Observation:
    """Fold outcomes into one envelope.

    ZERO outcomes is a WARNING, not a pass: an empty run reports no failures, which is exactly
    how a broken selector reads as green.
    """
    if not outcomes:
        return warning(
            "0 eval rows ran — an empty run is a selector failure, not a green result",
            next_actions=("check the catalogue and the live filter",),
        )
    failed = [o for o in outcomes if not o.passed]
    if not failed:
        return success(
            f"{len(outcomes)}/{len(outcomes)} regression rows passed",
            next_actions=("none — the regression suite is green",),
        )
    names = ", ".join(o.row_id for o in failed)
    return error(
        f"{len(outcomes) - len(failed)}/{len(outcomes)} rows passed; FAILED: {names}",
        ErrorDetail(
            code="policy-violation",
            root_cause="; ".join(f"{o.row_id}: {o.detail}" for o in failed),
            retry_instruction=(
                "do NOT re-run to see if it passes: each row encodes a measured past failure, "
                "so a red row means the protection is gone"
            ),
            stop_condition="stop and restore the protection; the suite is not retry-flaky",
        ),
        next_actions=(f"restore the protection behind {names}",),
    )


def _observe(row: EvalRow, *, passed: bool, detail: str) -> Observation:
    if passed:
        return success(
            f"{row.id} passed: {row.title}",
            next_actions=("none",),
            artifacts=(),
        )
    return error(
        f"{row.id} FAILED: {row.title}",
        ErrorDetail(
            code="policy-violation",
            root_cause=f"{detail} (measured failure: {row.measured_failure})",
            retry_instruction=(
                "do NOT retry: this row went red because a protection was removed, "
                "not because of a transient"
            ),
            stop_condition=f"stop until the RED condition no longer holds: {row.red_condition}",
        ),
        next_actions=(f"restore the protection behind {row.id}",),
    )
