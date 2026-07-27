"""DISPATCH PLANNING -- rail row + prompt -> a validated plan. PURE: no I/O, no clock.

Three agentspec facilities do the actual deciding here, and agentrail reimplements none of
them: :func:`agentspec.dispatchpolicy.check_dispatch` gates the dispatch shape,
:func:`agentspec.argv.build_for_rail` builds and length-checks argv (and refuses a prompt on
it), and :func:`agentspec.retry.plan_retry` owns the one-shot ``win-arg-limit`` retry.

THE SPILL is agentrail's own job, and the reason the argv enum never has to widen. A rail row
declares what its CLI natively accepts; when that is ``"argv"``, :func:`spill_transport` maps
it onto a legal transport instead:

* a row with a ``prompt_flag`` spills to a FILE (``--prompt-file <path>``: the path is short,
  the prompt is not on the command line);
* a row without one spills to STDIN.

Measured relevance: ``grok`` really does accept ``-p/--single <PROMPT>`` and a bare positional
prompt, and ``gemini``'s one-shot is argv-shaped. Using either would recreate the measured
``os error 206`` at ``payload_len=34472``. The spill is what makes "config row, not new code"
safe for a CLI that wants the wrong thing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from agentspec.argv import ArgvPlan, ArgvTooLong, build_for_rail
from agentspec.dispatchpolicy import check_dispatch
from agentspec.retry import RetryDecision, plan_retry

from agentrail.rails import ConfigError, RailRow, checked_marker_id

WIN_ARG_LIMIT = "win-arg-limit"
"""Imported semantics, local label: the string itself is a MEMBER of agentspec's closed
taxonomy (``tests/test_no_rival_core.py`` asserts that), not a rival vocabulary."""


_UNIT_ID_FILENAME_TRAPS: tuple[str, ...] = ("/", "\\", ":")
"""Characters that stop a unit id being a single, contained filename COMPONENT."""


def checked_unit_id(unit_id: str) -> str:
    """Validate a unit id ONCE, at the boundary, against BOTH contracts that bind it.

    RULE 1 -- can agentspec render it as a marker? Not decided here: it is delegated to
    :func:`agentrail.rails.checked_marker_id`, which calls agentspec's own renderer.

    RULE 2 -- is it a contained FILENAME? This one is agentrail's own, and is not a duplicate
    of anything agentspec owns, because only agentrail turns the id into a path:
    ``<spill_dir>/<unit_id>.prompt.txt``. agentspec's rule cannot cover it -- ``/`` and ``:``
    are printable and whitespace-free, so agentspec (correctly, for a marker) accepts them.

    MEASURED, both traps, with a recording filesystem:

    * ``unit_id="../../../../evil/pwned"`` writes to
      ``S:/spill/../../../../evil/pwned.prompt.txt`` -- outside the declared ``--spill-dir``,
      creating directories and truncating any ``*.prompt.txt`` already there;
    * ``unit_id="C:evil"`` is worse and silent: Windows reads ``C:evil.prompt.txt`` as a
      DRIVE-RELATIVE path, so ``spill/C:evil.prompt.txt`` landed at the current directory of
      drive ``C:`` with no error and an empty spill dir.

    Refused rather than sanitised: a rewritten id would no longer match the ``SUCCESS:<id>`` /
    ``FAILED:<id>`` marker the caller is told to grep for, which trades one silent mismatch
    for another. :mod:`agentrail.deploy` already carries a guard for this data-loss class; the
    spill write is the other place that needed one.
    """
    checked_marker_id(unit_id, field="unit_id")
    traps = tuple(char for char in _UNIT_ID_FILENAME_TRAPS if char in unit_id)
    if traps:
        raise ConfigError(
            f"unit_id {unit_id!r} contains {list(traps)}: the id becomes the spill filename "
            f"<spill_dir>/<unit_id>.prompt.txt, and a separator or drive letter escapes the "
            f"declared --spill-dir. Use a plain identifier."
        )
    return unit_id


class DispatchRefused(ValueError):
    """The dispatch SHAPE is illegal -- checked before any rail is touched.

    DELIBERATELY declared here and not imported from
    :class:`agentspec.evals.fake_rail.DispatchRefused`, which carries the same name and the
    same ``violations`` field. The POLICY is shared -- both call
    :func:`agentspec.dispatchpolicy.check_dispatch`, which is the part that must not fork --
    but ``agentspec.evals`` is agentspec's hermetic TEST-DOUBLE subpackage, and importing a
    test double into a production dispatch shell would be a worse coupling than a four-line
    exception wrapper. Only the wrapper is duplicated; the decision is not.
    """

    reason = "policy-violation"

    def __init__(self, violations: tuple[str, ...]) -> None:
        self.violations = violations
        super().__init__(f"policy-violation: dispatch refused {list(violations)}")


@dataclass(frozen=True, slots=True)
class PromptSpill:
    """A prompt that must be written to disk before the argv in the plan can be run.

    Carried as DATA so the planner stays pure: :mod:`agentrail.runner` performs the write.

    NOT deleted afterwards, deliberately. The path is reported in the envelope's ``artifacts``
    as ``prompt=<path>`` precisely so a failed dispatch can be reproduced byte-for-byte, and a
    package whose reason for existing is "do not discard a completed run's evidence" should not
    delete that evidence on the way out. Retention is the caller's policy: ``--spill-dir``
    exists so it can point at a directory it already sweeps. The containment rule in
    :func:`checked_unit_id` is what keeps the files inside that directory.
    """

    path: str
    text: str


@dataclass(frozen=True, slots=True)
class DispatchPlan:
    """Everything a spawn needs, and nothing it has to work out for itself."""

    unit_id: str
    rail_name: str
    exe: str
    argv_plan: ArgvPlan
    native_transport: str
    transport: str
    spilled: bool
    spill: PromptSpill | None
    receipt_path: str | None
    timeout_s: int
    attempt: int
    retries: tuple[RetryDecision, ...] = ()

    @property
    def argv(self) -> tuple[str, ...]:
        return self.argv_plan.argv

    @property
    def stdin_payload(self) -> str | None:
        return self.argv_plan.stdin_payload


def spill_transport(row: RailRow) -> tuple[str, bool]:
    """Map ``row.native_transport`` onto an agentspec-legal transport.

    Returns ``(transport, spilled)``. ``spilled`` is True only when the row's CLI wanted the
    prompt on argv and agentrail routed it elsewhere.
    """
    if row.native_transport == "argv":
        return ("file" if row.prompt_flag else "stdin", True)
    return (row.native_transport, False)


def build_plan(
    row: RailRow,
    exe: str,
    *,
    unit_id: str,
    prompt: str,
    spill_dir: str,
    receipt_path: str | None = None,
    timeout_s: int | None = None,
    flags: Sequence[str] = (),
    awaited: bool = True,
    background: bool = False,
    attempt: int = 1,
    force_transport: str | None = None,
) -> DispatchPlan:
    """Build ONE plan. Raises rather than degrading -- every raise is a taxonomy reason.

    ``force_transport`` exists for :func:`plan_with_retry` to re-plan onto a shorter transport;
    production callers leave it ``None`` and let :func:`spill_transport` decide.
    """
    checked_unit_id(unit_id)
    effective_timeout = row.default_timeout_s if timeout_s is None else timeout_s

    violations = check_dispatch(
        background=background, timeout_s=effective_timeout, awaited=awaited
    )
    if violations:
        raise DispatchRefused(violations)

    transport, spilled = spill_transport(row)
    if force_transport is not None:
        transport = force_transport

    spill: PromptSpill | None = None
    prompt_path: str | None = None
    if transport == "file":
        prompt_path = _join(spill_dir, f"{unit_id}.prompt.txt")
        spill = PromptSpill(path=prompt_path, text=prompt)

    argv_plan = build_for_rail(
        row.rail_spec(exe, transport=transport),
        prompt=prompt,
        prompt_path=prompt_path,
        flags=_flags(row, flags, receipt_path),
    )
    return DispatchPlan(
        unit_id=unit_id,
        rail_name=row.name,
        exe=exe,
        argv_plan=argv_plan,
        native_transport=row.native_transport,
        transport=transport,
        spilled=spilled,
        spill=spill,
        receipt_path=receipt_path,
        timeout_s=effective_timeout,
        attempt=attempt,
    )


def plan_with_retry(
    row: RailRow,
    exe: str,
    *,
    unit_id: str,
    prompt: str,
    spill_dir: str,
    receipt_path: str | None = None,
    timeout_s: int | None = None,
    flags: Sequence[str] = (),
    awaited: bool = True,
    background: bool = False,
    attempt: int = 1,
) -> DispatchPlan:
    """Build a plan, applying agentspec's ONE-SHOT ``win-arg-limit`` retry if argv is too long.

    The prompt is already off argv by construction, so an over-cap command line means the FLAGS
    are too long. The only lever agentrail owns is the transport: the FILE form costs
    ``<prompt_flag> <path>`` on the command line and the STDIN form costs nothing, so the retry
    re-plans onto stdin. If the plan is already on stdin there is no shorter form and the
    :class:`agentspec.argv.ArgvTooLong` propagates -- a failure agentrail cannot fix must not be
    dressed up as one it retried.

    ``attempt`` is passed THROUGH to :func:`agentspec.retry.plan_retry` rather than pinned to 1,
    so a caller re-planning after a dispatch that already burned the retry gets agentspec's
    real answer (``retry=False``, "already retried once; stop") instead of an unbounded loop.
    Pinning it would also have made the ``not decision.retry`` arm below unreachable -- dead
    defensive code that looks like a check and checks nothing.
    """
    try:
        return build_plan(
            row,
            exe,
            unit_id=unit_id,
            prompt=prompt,
            spill_dir=spill_dir,
            receipt_path=receipt_path,
            timeout_s=timeout_s,
            flags=flags,
            awaited=awaited,
            background=background,
            attempt=attempt,
        )
    except ArgvTooLong:
        decision = plan_retry(WIN_ARG_LIMIT, attempt=attempt)
        shorter = _shorter_transport(spill_transport(row)[0])
        if not decision.retry or shorter is None:
            raise
        retried = build_plan(
            row,
            exe,
            unit_id=unit_id,
            prompt=prompt,
            spill_dir=spill_dir,
            receipt_path=receipt_path,
            timeout_s=timeout_s,
            flags=flags,
            awaited=awaited,
            background=background,
            attempt=decision.next_attempt,
            force_transport=shorter,
        )
        return replace(retried, retries=(decision,))


def _shorter_transport(transport: str) -> str | None:
    """The transport that puts LESS on the command line, or ``None`` when already minimal."""
    return "stdin" if transport == "file" else None


def _flags(
    row: RailRow, extra: Sequence[str], receipt_path: str | None
) -> tuple[str, ...]:
    """Row base flags, then caller flags, then the receipt flag pair when both are present.

    Hardening is NOT added here: :func:`agentspec.argv.build_for_rail` appends and then
    VERIFIES it, and adding it twice would defeat that verification.
    """
    flags = (*row.base_flags, *extra)
    if row.receipt_flag is not None and receipt_path is not None:
        flags = (*flags, row.receipt_flag, receipt_path)
    return flags


_PATH_SEPARATORS = "/\\"


def _join(directory: str, name: str) -> str:
    """Join with a forward slash, which every Windows API and every POSIX shell accepts.

    Deliberately not ``os.path.join``: the plan is DATA that a test compares byte-for-byte, and
    a platform-dependent separator would make the same plan render two ways.
    """
    return f"{directory.rstrip(_PATH_SEPARATORS)}/{name}"
