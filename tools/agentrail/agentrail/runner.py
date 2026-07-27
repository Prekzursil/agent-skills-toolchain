"""THE IMPURE SHELL -- the only module that binds a real disk, a real clock, a real process.

Everything above it (rails / resolve / plan / report / deploy) sees Protocols, which is what
makes 100% line+branch coverage reachable with ZERO ``# pragma: no cover``. The three real
bindings here are each measured WITHOUT breaking hermeticity:

* :class:`LocalFileSystem` -- driven against a pytest ``tmp_path``. Real disk, no network, no
  spawn, deterministic.
* :class:`MonotonicClock` -- one stdlib call; asserted monotonic and non-negative.
* :class:`SubprocessSpawn` -- takes the ``run`` callable as a CONSTRUCTOR argument defaulting
  to :func:`subprocess.run`, so the gated suite injects a fake and drives every branch,
  including each exception arm, while spawning nothing. The real default is exercised only by
  the ``live``-marked rows, which CI deselects with ``-m "not live"``.

:func:`dispatch` is the orchestration and is itself pure-with-ports, so the whole
resolve -> plan -> spill -> spawn -> receipt -> judge sequence is testable end to end against
fakes.
"""

from __future__ import annotations

import errno
import glob as globlib
import os.path as ospath
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agentspec.argv import ArgvTooLong
from agentspec.clock import Clock, elapsed_ms
from agentspec.taxonomy import timeout as timeout_reason

from agentrail.plan import DispatchPlan, DispatchRefused, plan_with_retry
from agentrail.ports import (
    CollectingWarnings,
    RailFileSystem,
    Spawn,
    SpawnOutcome,
    WarningSink,
)
from agentrail.rails import RailRow
from agentrail.report import (
    RailReport,
    argv_too_long,
    judge_result,
    refusal,
    resolution_failure,
    transport_failure,
)
from agentrail.resolve import ExecutableNotFound, Resolution, resolve

WIN_ERROR_FILENAME_EXCED_RANGE = 206
"""The Windows error behind the MEASURED ``os error 206`` at ``payload_len=34472``."""


class RunCallable(Protocol):
    """The injected :func:`subprocess.run` seam.

    Two shape details are load-bearing and were settled by a both-states basedpyright probe,
    not by guessing:

    * the first parameter is POSITIONAL-ONLY (``/``) -- :func:`subprocess.run` names it
      ``args``, and a differently-named protocol parameter fails on a NAME mismatch that reads
      like a type error;
    * the return is the CONCRETE :class:`subprocess.CompletedProcess`, not a structural
      "has returncode/stdout/stderr" protocol. The structural form is REJECTED by basedpyright
      1.39.8 (measured: identical protocol, only the return type differing, 1 error vs 0). The
      concrete type is also the more faithful seam -- the fake returns exactly what the real
      call returns, and constructing a ``CompletedProcess`` spawns nothing.
    """

    def __call__(
        self,
        args: Sequence[str],
        /,
        *,
        input: bytes | None,
        capture_output: bool,
        timeout: int,
        cwd: str | None,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]: ...


class LocalFileSystem:
    """The real :class:`~agentrail.ports.RailFileSystem`. Thin by design."""

    def glob(self, pattern: str) -> tuple[str, ...]:
        """Sorted matches, each normalised to ONE separator style.

        ``glob`` echoes the pattern's literal segments verbatim and joins the wildcard ones with
        ``os.sep``, so a forward-slash pattern on Windows returns a mixed
        ``C:\\Users\\me/AppData/...\\bin\\codex.exe``. That is functional but it lands in the
        result envelope's artifacts, where an operator has to read it.
        """
        return tuple(sorted(ospath.normpath(match) for match in globlib.glob(pattern)))

    def is_file(self, path: str) -> bool:
        return Path(path).is_file()

    def read_bytes(self, path: str) -> bytes | None:
        target = Path(path)
        if not target.is_file():
            return None
        return target.read_bytes()

    def write_text(self, path: str, text: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


class MonotonicClock:
    """The real :class:`agentspec.clock.Clock`. agentspec ships none on purpose."""

    def now_ms(self) -> int:
        return time.monotonic_ns() // 1_000_000


@dataclass(frozen=True, slots=True)
class SubprocessSpawn:
    """The real :class:`~agentrail.ports.Spawn`, with the stdlib call injected as a seam.

    NEVER backgrounds and ALWAYS bounds: ``timeout`` is mandatory upstream
    (:func:`agentspec.dispatchpolicy.check_dispatch` emits ``missing-timeout``), and every
    failure is mapped onto the CLOSED taxonomy rather than leaking an OSError to the caller.
    """

    run: RunCallable = subprocess.run

    def __call__(
        self,
        *,
        argv: Sequence[str],
        stdin_payload: str | None,
        timeout_s: int,
        cwd: str | None,
    ) -> SpawnOutcome:
        payload = None if stdin_payload is None else stdin_payload.encode("utf-8")
        try:
            completed = self.run(
                tuple(argv),
                input=payload,
                capture_output=True,
                timeout=timeout_s,
                cwd=cwd,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return SpawnOutcome(
                exit_code=-1,
                error_reason=timeout_reason(timeout_s),
                detail=f"the rail did not finish within {timeout_s}s and was killed",
            )
        except OSError as exc:
            return SpawnOutcome(
                exit_code=-1,
                error_reason=_os_error_reason(exc),
                detail=f"{type(exc).__name__}: {exc}",
            )
        return SpawnOutcome(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def dispatch(
    row: RailRow,
    *,
    unit_id: str,
    prompt: str,
    spill_dir: str,
    fs: RailFileSystem,
    spawn: Spawn,
    clock: Clock,
    receipt_path: str | None = None,
    timeout_s: int | None = None,
    flags: Sequence[str] = (),
    cwd: str | None = None,
    awaited: bool = True,
    background: bool = False,
    sink: WarningSink | None = None,
) -> RailReport:
    """Resolve, plan, spill, spawn, collect the receipt and JUDGE. Every edge is a port.

    Returns a :class:`~agentrail.report.RailReport` on EVERY path -- there is no route out of
    this function that yields an unenveloped failure.
    """
    warnings = CollectingWarnings() if sink is None else sink
    try:
        resolution = resolve(row, fs, sink=warnings)
    except ExecutableNotFound as exc:
        return resolution_failure(unit_id, row.name, exc.reason, tried=exc.tried)

    try:
        plan = plan_with_retry(
            row,
            resolution.exe,
            unit_id=unit_id,
            prompt=prompt,
            spill_dir=spill_dir,
            receipt_path=receipt_path,
            timeout_s=timeout_s,
            flags=flags,
            awaited=awaited,
            background=background,
        )
    except DispatchRefused as exc:
        return refusal(unit_id, exc.violations)
    except ArgvTooLong as exc:
        return argv_too_long(unit_id, cmdline_len=exc.cmdline_len, cap=exc.cap)

    return run_plan(
        plan,
        row=row,
        resolution=resolution,
        fs=fs,
        spawn=spawn,
        clock=clock,
        cwd=cwd,
    )


def run_plan(
    plan: DispatchPlan,
    *,
    row: RailRow,
    resolution: Resolution,
    fs: RailFileSystem,
    spawn: Spawn,
    clock: Clock,
    cwd: str | None = None,
) -> RailReport:
    """Execute an already-built plan. Split out so a caller can inspect the plan first."""
    if plan.spill is not None:
        fs.write_text(plan.spill.path, plan.spill.text)

    started = clock.now_ms()
    outcome = spawn(
        argv=plan.argv,
        stdin_payload=plan.stdin_payload,
        timeout_s=plan.timeout_s,
        cwd=cwd,
    )
    wall_ms = elapsed_ms(started, clock.now_ms())
    artifacts = _artifacts(plan, resolution)

    if outcome.error_reason is not None:
        return _transport_report(plan, outcome.error_reason, outcome.detail, artifacts)

    return _judge(plan, row, outcome, fs, wall_ms=wall_ms, artifacts=artifacts)


def _judge(
    plan: DispatchPlan,
    row: RailRow,
    outcome: SpawnOutcome,
    fs: RailFileSystem,
    *,
    wall_ms: int,
    artifacts: tuple[str, ...],
) -> RailReport:
    """Collect the receipt, then hand it to agentspec's AND-gate. Imports no policy of its own."""
    receipt = _receipt_bytes(plan, outcome, fs)
    return judge_result(
        plan.unit_id,
        exit_code=outcome.exit_code,
        receipt_bytes=receipt,
        spec=row.receipt_spec(),
        progress=outcome.stderr.decode("utf-8", errors="replace"),
        wall_ms=wall_ms,
        artifacts=artifacts,
    )


def _receipt_bytes(
    plan: DispatchPlan, outcome: SpawnOutcome, fs: RailFileSystem
) -> bytes | None:
    """The receipt is the declared FILE when the row asked for one, else stdout.

    A declared-but-absent receipt file returns ``None`` and becomes ``receipt-missing`` in the
    oracle. It deliberately does NOT silently fall back to stdout: a rail told to write a
    receipt and did not is severed, and reading its chatter instead is how a progress stream
    gets reported as an answer.
    """
    if plan.receipt_path is not None:
        return fs.read_bytes(plan.receipt_path)
    return outcome.stdout


def _transport_report(
    plan: DispatchPlan, reason: str, detail: str, artifacts: tuple[str, ...]
) -> RailReport:
    """The reason is passed in NARROWED to ``str`` by the caller's ``is not None`` check.

    Deliberately not ``outcome.error_reason or "spawn-failed"`` inside this function: that
    fallback would be unreachable defensive code -- a check that looks like a check and checks
    nothing -- and unreachable code is exactly what a 100% bar is supposed to surface.
    """
    return transport_failure(
        plan.unit_id,
        reason,
        detail=detail,
        next_action=f"inspect the {plan.rail_name!r} rail invocation, then re-dispatch",
        retry_instruction=(
            "re-dispatch the SAME unit at most once, in the FOREGROUND, with an explicit "
            "timeout; never widen the transport to put the prompt on argv"
        ),
        stop_condition=(
            f"stop after 1 retry and report FAILED {plan.unit_id} {reason}"
        ),
        artifacts=artifacts,
    )


def _artifacts(plan: DispatchPlan, resolution: Resolution) -> tuple[str, ...]:
    """What an operator needs to look at, in a stable order."""
    items = [f"exe={resolution.exe}", f"resolved-by={resolution.source}"]
    if plan.spill is not None:
        items.append(f"prompt={plan.spill.path}")
    if plan.receipt_path is not None:
        items.append(f"receipt={plan.receipt_path}")
    if plan.spilled:
        items.append(f"spilled-from={plan.native_transport}->{plan.transport}")
    items.extend(f"retry={decision.rationale}" for decision in plan.retries)
    items.extend(resolution.warnings)
    return tuple(items)


def _os_error_reason(exc: OSError) -> str:
    """Map an OSError onto the CLOSED taxonomy. Never invents a code."""
    winerror: object = getattr(exc, "winerror", None)
    if winerror == WIN_ERROR_FILENAME_EXCED_RANGE or exc.errno == errno.E2BIG:
        return "win-arg-limit"
    return "spawn-failed"


@dataclass(frozen=True, slots=True)
class Ports:
    """The production wiring, bundled so adding a port is not a signature change everywhere.

    A caller that wants fakes constructs this with fakes; :func:`default_ports` is the only
    place the real trio is assembled.
    """

    fs: RailFileSystem
    spawn: Spawn
    clock: Clock


def default_ports() -> Ports:
    """The real port trio. The single seam between agentrail and the machine it runs on."""
    return Ports(fs=LocalFileSystem(), spawn=SubprocessSpawn(), clock=MonotonicClock())
