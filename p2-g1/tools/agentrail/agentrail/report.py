"""REPORTING -- raw rail output -> the agentspec verdict, envelope and terminal marker. PURE.

There is NO rival AND-gate here and NO rival reason string. Every success/failure decision is
:func:`agentspec.oracle.judge`; every envelope is built by :mod:`agentspec.envelope`; every
reason agentrail can emit is in :data:`AGENTRAIL_REASONS`, which
``tests/test_no_rival_core.py`` asserts is a SUBSET of :data:`agentspec.taxonomy.REASONS`.

The envelope contract holds on BOTH paths. Success and error alike carry ``status``,
``summary``, ``next_actions`` and ``artifacts``; every error additionally carries
``error{code, root_cause, retry_instruction, stop_condition}``. "Error-only output without next
steps" is a named anti-pattern, so :func:`agentspec.envelope.error` refuses an empty
``next_actions`` and every constructor below passes a real one.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentspec.envelope import ErrorDetail, Observation, error, validate_observation
from agentspec.oracle import RailResult, Verdict, judge, observe
from agentspec.spec import ReceiptSpec
from agentspec.taxonomy import family, is_reason
from agentspec.terminal import failure_line, terminal_line

AGENTRAIL_REASONS: tuple[str, ...] = (
    "env-missing",
    "policy-violation",
    "spawn-failed",
    "timeout",
    "win-arg-limit",
)
"""The reasons agentrail's TRANSPORT can originate, sorted.

Everything else a dispatch can report comes out of :func:`agentspec.oracle.judge` and is
agentspec's to name. This tuple exists so the subset property is machine-checkable rather than
asserted in prose -- a reason string outside agentspec's closed set is a mutation row.
"""


class UnknownReason(ValueError):
    """A transport tried to report a reason outside agentspec's closed taxonomy.

    Raised, not coerced: silently rewriting an unknown code to a known one is how a closed
    vocabulary stops being closed, and the caller that minted it is the thing to fix.
    """

    reason = "policy-violation"


@dataclass(frozen=True, slots=True)
class RailReport:
    """One dispatch, fully judged: the verdict, the envelope and the terminal marker.

    ``verdict`` is ``None`` for a TRANSPORT failure -- no process produced a result, so there
    was nothing for the oracle to judge. The envelope and the marker are always present.
    """

    unit_id: str
    observation: Observation
    terminal: str
    verdict: Verdict | None = None

    @property
    def ok(self) -> bool:
        return self.observation.status == "success"

    def as_dict(self) -> dict[str, object]:
        """The wire form: the four envelope fields (plus ``error``) and the marker."""
        payload: dict[str, object] = dict(self.observation.as_dict())
        payload["terminal"] = self.terminal
        return payload


def judge_result(
    unit_id: str,
    *,
    exit_code: int,
    receipt_bytes: bytes | None,
    spec: ReceiptSpec,
    progress: str = "",
    wall_ms: int = 0,
    artifacts: tuple[str, ...] = (),
) -> RailReport:
    """Run agentspec's six-clause AND-gate over one rail result and project it.

    ``progress`` is DIAGNOSTICS. It is passed through to the :class:`RailResult` and is never
    read as the answer -- exit 0 with a progress body is SEVERED, not SUCCESS.
    """
    result = RailResult(
        exit_code=exit_code,
        receipt_bytes=receipt_bytes,
        progress=progress,
        wall_ms=wall_ms,
    )
    verdict = judge(unit_id, result, spec)
    return RailReport(
        unit_id=unit_id,
        observation=checked_envelope(observe(verdict, artifacts=artifacts)),
        terminal=terminal_line(verdict),
        verdict=verdict,
    )


def transport_failure(
    unit_id: str,
    reason: str,
    *,
    detail: str,
    next_action: str,
    retry_instruction: str,
    stop_condition: str,
    artifacts: tuple[str, ...] = (),
) -> RailReport:
    """Render a failure that happened BEFORE or INSTEAD of a rail result.

    Refuses a reason outside the closed taxonomy: an envelope carrying an unmatched code is
    invisible to every consumer that greps the taxonomy, which is the failure this guards.

    The MARKER carries ``family(reason)`` while the ENVELOPE keeps the full parametrised code:
    ``env-missing-codex`` renders as ``FAILED:<id> env-missing`` but stays ``env-missing-codex``
    in ``error.code``. That is a deliberate split, not a constraint --
    :func:`agentspec.terminal.failure_line` is family-aware and would accept the parametrised
    form. The marker is the line a consumer GREPS, so it is kept at the closed-set granularity
    a grep can enumerate; the parameter, which is unbounded, stays in the field built for it.
    """
    if not is_reason(reason):
        raise UnknownReason(
            f"reason {reason!r} is not in the closed agentspec taxonomy; "
            f"transports may only originate {list(AGENTRAIL_REASONS)}"
        )
    observation = error(
        f"{unit_id}: {reason}",
        ErrorDetail(
            code=reason,
            root_cause=detail,
            retry_instruction=retry_instruction,
            stop_condition=stop_condition,
        ),
        next_actions=(next_action,),
        artifacts=artifacts,
    )
    return RailReport(
        unit_id=unit_id,
        observation=checked_envelope(observation),
        terminal=failure_line(unit_id, family(reason)),
    )


def resolution_failure(
    unit_id: str, rail_name: str, reason: str, *, tried: tuple[str, ...]
) -> RailReport:
    """No executable resolved. The rail was never touched, so this is not a rail failure."""
    return transport_failure(
        unit_id,
        reason,
        detail=(
            f"rail {rail_name!r} did not resolve to an executable; tried {list(tried)}. "
            f"The globs are deliberate -- the vendor path carries a package version and a "
            f"target triple, both of which move."
        ),
        next_action=f"install or repair the {rail_name!r} CLI, then re-run",
        retry_instruction=(
            "do NOT retry as-is: nothing about the dispatch will change until the executable "
            "exists. Re-run only after `<rail> --version` succeeds."
        ),
        stop_condition=f"stop immediately and report FAILED {unit_id} {reason}",
        artifacts=tried,
    )


def refusal(unit_id: str, violations: tuple[str, ...]) -> RailReport:
    """The dispatch SHAPE was illegal. agentspec.dispatchpolicy named the violations."""
    return transport_failure(
        unit_id,
        "policy-violation",
        detail=f"pre-dispatch policy refused this shape: {list(violations)}",
        next_action=f"fix the dispatch shape ({list(violations)}) and re-plan",
        retry_instruction=(
            "unrecoverable by retry -- the CALLER must be fixed. A backgrounded dispatch that "
            "something awaits is structurally unreachable to its barrier, and a dispatch with "
            "no explicit timeout has no bound at all."
        ),
        stop_condition=f"stop immediately and report FAILED {unit_id} policy-violation",
        artifacts=violations,
    )


def argv_too_long(unit_id: str, *, cmdline_len: int, cap: int) -> RailReport:
    """The command line exceeded the cap and no shorter transport was available."""
    return transport_failure(
        unit_id,
        "win-arg-limit",
        detail=(
            f"the rendered command line is {cmdline_len} chars against a cap of {cap}. The "
            f"prompt is NOT the cause -- it never reaches argv -- so the rail's flags are."
        ),
        next_action="shorten the rail's base_flags in rails.toml, then re-plan",
        retry_instruction=(
            "agentspec.retry.plan_retry allows exactly one automatic retry, and it was already "
            "spent re-planning onto stdin. Do not loop."
        ),
        stop_condition=f"stop immediately and report FAILED {unit_id} win-arg-limit",
    )


def checked_envelope(observation: Observation) -> Observation:
    """Fail loudly on a malformed envelope instead of shipping one.

    :func:`agentspec.envelope.validate_observation` is the same validator every other lane
    uses, so a field dropped here is caught by the shared rule rather than a local opinion.
    """
    violations = validate_observation(observation)
    if violations:
        raise UnknownReason(f"malformed observation envelope: {list(violations)}")
    return observation
