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
import threading
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


class LoopError(Exception):
    def __init__(self, message: str, code: str = "loop-error") -> None:
        super().__init__(f"{code}: {message}" if code not in message else message)
        self.code = code


@dataclass
class Loop:
    """Bounded loop node. max_iterations is required to represent the node."""

    id: str
    body: tuple
    convergence_expr: dict | None
    max_iterations: int | None
    on_bound_reached: str = "abort"

    def __post_init__(self) -> None:
        if self.max_iterations is None and self.convergence_expr is None:
            raise LoopError("loop is unbounded", code="loop-unbounded")


@dataclass
class LoopIteration:
    index: int
    predicate_verdict: bool
    predicate_inputs: dict
    state: dict


@dataclass
class LoopResult:
    status: str
    converged: bool
    iterations: list
    final_state: dict
    bound: int | None


def _lookup(state: dict, path: str):
    cur: object = state
    for part in str(path).split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _apply_body(state: dict, body: tuple) -> dict:
    out = dict(state)
    for step in body:
        if not isinstance(step, dict):
            continue
        op = step.get("op")
        if op == "incr":
            path = str(step.get("path") or "n")
            by = int(step.get("by") or 1)
            out[path] = int(out.get(path) or 0) + by
        elif op == "noop":
            continue
    return out


def _eval_expr(expr: dict | None, state: dict) -> tuple[bool, dict]:
    expr = expr or {"op": "never"}
    op = expr.get("op")
    bindings = dict(state)
    inputs = {"expr": dict(expr), "bindings": bindings}
    if op == "never":
        return False, inputs
    if op == "gte":
        path = str(expr.get("path") or "n")
        value = expr.get("value")
        got = _lookup(state, path)
        return bool(got is not None and got >= value), inputs
    return False, inputs


def evaluate_from_inputs(inputs: dict) -> bool:
    if not isinstance(inputs, dict) or "bindings" not in inputs:
        raise LoopError("bindings required", code="loop-inputs-missing-bindings")
    expr = (inputs or {}).get("expr") or {}
    bindings = dict(inputs.get("bindings") or {})
    verdict, _ = _eval_expr(expr, bindings)
    return verdict


def execute_loop(loop: Loop, initial: dict) -> LoopResult:
    if loop.max_iterations is None:
        raise LoopError("runtime bound required", code="loop-bound-required-at-runtime")
    bound = int(loop.max_iterations)
    state = dict(initial)
    iterations: list[LoopIteration] = []
    for i in range(1, bound + 1):
        state = _apply_body(state, tuple(loop.body or ()))
        verdict, inputs = _eval_expr(loop.convergence_expr, state)
        iterations.append(
            LoopIteration(index=i, predicate_verdict=verdict, predicate_inputs=inputs, state=dict(state))
        )
        if verdict:
            return LoopResult(
                status="CONVERGED",
                converged=True,
                iterations=iterations,
                final_state=dict(state),
                bound=bound,
            )
    status = "FAILED_BOUND" if loop.on_bound_reached == "fail" else "BOUND_REACHED"
    return LoopResult(
        status=status,
        converged=False,
        iterations=iterations,
        final_state=dict(state),
        bound=bound,
    )


COMPLETED = "completed"
TIMEOUT = "timeout"
TIMEOUT_TYPED = "timeout-typed"
TIMEOUT_UNTYPED = "timeout-untyped"
ABSENT_NOTE = "ABSENT-terminal-record"


@dataclass(frozen=True, slots=True)
class CohortUnit:
    """One unit of a cohort: does ``work_s`` of work, or hangs for ``hang_s`` if ``hung``.

    ``timeout_s`` is the unit's OWN declared timeout; the isolated runner never lets a
    sibling's hang hold this unit past it.
    """

    id: str
    timeout_s: float
    work_s: float
    hang_s: float
    hung: bool = False

    def planned_duration_s(self) -> float:
        return self.hang_s if self.hung else self.work_s


@dataclass(slots=True)
class LedgerEntry:
    """Terminal record for one unit, with timestamps relative to the cohort start."""

    unit_id: str
    pipeline_id: str
    terminal_state: str
    timeout_class: str | None
    timeout_s: float
    started_s: float
    ended_s: float
    note: str = ""

    @property
    def duration_s(self) -> float:
        return max(0.0, self.ended_s - self.started_s)


@dataclass(slots=True)
class CohortLedger:
    """Every unit's terminal record plus how long the barrier held the cohort."""

    runner: str
    entries: list[LedgerEntry]
    barrier_wait_s: float

    def by_id(self) -> dict[str, LedgerEntry]:
        return {e.unit_id: e for e in self.entries}


def make_cohort(
    n: int = 50,
    hang_at: int | None = None,
    timeout_s: float = 0.4,
    work_s: float = 0.001,
    hang_s: float = 1.2,
) -> list[CohortUnit]:
    """Build ``n`` units ``U-0000..``; unit ``hang_at`` (if given) hangs for ``hang_s``."""
    return [
        CohortUnit(
            id=f"U-{i:04d}",
            timeout_s=float(timeout_s),
            work_s=float(work_s),
            hang_s=float(hang_s),
            hung=(hang_at is not None and i == int(hang_at)),
        )
        for i in range(int(n))
    ]


def _unit_work(unit: CohortUnit, cancel: threading.Event) -> None:
    """The unit's body: a sleep that a cancel can cut short. Hung units ignore nothing here;
    the isolated runner stops WAITING for them, and cancels them so the thread can exit."""
    cancel.wait(unit.planned_duration_s())


def _fill_absent(units: Sequence[CohortUnit], have: dict[str, LedgerEntry], now_s: float) -> None:
    """A unit with no terminal record is recorded as ABSENT, never silently dropped."""
    for unit in units:
        if unit.id not in have:
            have[unit.id] = LedgerEntry(
                unit_id=unit.id,
                pipeline_id="",
                terminal_state=TIMEOUT,
                timeout_class=TIMEOUT_UNTYPED,
                timeout_s=unit.timeout_s,
                started_s=0.0,
                ended_s=now_s,
                note=ABSENT_NOTE,
            )


class IsolatedPipelineRunner:
    """Per-unit pipeline that cannot be deadlocked by a hung sibling.

    Every unit runs on its own thread with its OWN deadline. The barrier is the moment the
    last deadline-or-completion has been recorded, so a hung unit costs the cohort at most
    its declared ``timeout_s`` and is written as a TYPED timeout, not left absent.
    """

    def run_cohort(self, units: Sequence[CohortUnit]) -> CohortLedger:
        origin = time.monotonic()
        cancels: dict[str, threading.Event] = {}
        threads: dict[str, threading.Thread] = {}
        starts: dict[str, float] = {}
        for unit in units:
            cancel = threading.Event()
            thread = threading.Thread(
                target=_unit_work, args=(unit, cancel), name=f"pipe-{unit.id}", daemon=True
            )
            cancels[unit.id] = cancel
            threads[unit.id] = thread
            starts[unit.id] = time.monotonic() - origin
            thread.start()

        records: dict[str, LedgerEntry] = {}
        for unit in units:
            thread = threads[unit.id]
            deadline = starts[unit.id] + unit.timeout_s
            remaining = deadline - (time.monotonic() - origin)
            if remaining > 0:
                thread.join(remaining)
            ended = time.monotonic() - origin
            if thread.is_alive():
                cancels[unit.id].set()
                records[unit.id] = LedgerEntry(
                    unit_id=unit.id,
                    pipeline_id=thread.name,
                    terminal_state=TIMEOUT,
                    timeout_class=TIMEOUT_TYPED,
                    timeout_s=unit.timeout_s,
                    started_s=starts[unit.id],
                    ended_s=ended,
                    note=f"killed at declared timeout {unit.timeout_s}s",
                )
            else:
                records[unit.id] = LedgerEntry(
                    unit_id=unit.id,
                    pipeline_id=thread.name,
                    terminal_state=COMPLETED,
                    timeout_class=None,
                    timeout_s=unit.timeout_s,
                    started_s=starts[unit.id],
                    ended_s=ended,
                )
        barrier = time.monotonic() - origin
        _fill_absent(units, records, barrier)
        return CohortLedger(
            runner=type(self).__name__,
            entries=[records[u.id] for u in units],
            barrier_wait_s=barrier,
        )


class CoupledBarrierRunner:
    """Known-broken join-all barrier: a hung unit stalls the whole cohort.

    Kept as the negative control for :func:`assert_no_barrier_past_timeout`. Units are
    classified only after EVERY thread has joined, so the hung unit's real duration -- and
    the cohort's barrier wait -- exceed the declared timeout.
    """

    def run_cohort(self, units: Sequence[CohortUnit]) -> CohortLedger:
        origin = time.monotonic()
        never_cancel = threading.Event()
        threads: dict[str, threading.Thread] = {}
        starts: dict[str, float] = {}
        ends: dict[str, float] = {}
        lock = threading.Lock()

        def body(unit: CohortUnit) -> None:
            _unit_work(unit, never_cancel)
            with lock:
                ends[unit.id] = time.monotonic() - origin

        for unit in units:
            thread = threading.Thread(target=body, args=(unit,), name="barrier-shared", daemon=True)
            threads[unit.id] = thread
            starts[unit.id] = time.monotonic() - origin
            thread.start()
        for thread in threads.values():
            thread.join()
        barrier = time.monotonic() - origin

        records: dict[str, LedgerEntry] = {}
        for unit in units:
            ended = ends.get(unit.id, barrier)
            late = (ended - starts[unit.id]) > unit.timeout_s
            records[unit.id] = LedgerEntry(
                unit_id=unit.id,
                pipeline_id="barrier-shared",
                terminal_state=TIMEOUT if late else COMPLETED,
                timeout_class=TIMEOUT_TYPED if late else None,
                timeout_s=unit.timeout_s,
                started_s=starts[unit.id],
                ended_s=ended,
                note="classified after join-all" if late else "",
            )
        _fill_absent(units, records, barrier)
        return CohortLedger(
            runner=type(self).__name__,
            entries=[records[u.id] for u in units],
            barrier_wait_s=barrier,
        )


def summarize(ledger: CohortLedger) -> dict:
    """Counts a probe can assert on, all derived from the ledger rows."""
    entries = list(ledger.entries)
    completed = [e for e in entries if e.terminal_state == COMPLETED]
    timeouts = [e for e in entries if e.terminal_state == TIMEOUT]
    typed = [e for e in timeouts if e.timeout_class == TIMEOUT_TYPED]
    absent = [e for e in entries if e.note == ABSENT_NOTE]
    return {
        "runner": ledger.runner,
        "n": len(entries),
        "completed": len(completed),
        "timeout": len(timeouts),
        "timeout_typed": len(typed),
        "timeout_untyped": len(timeouts) - len(typed),
        "absent": len(absent),
        "pipeline_ids": len({e.pipeline_id for e in entries if e.pipeline_id}),
        "timeout_unit_ids": sorted(e.unit_id for e in timeouts),
        "completed_unit_ids": sorted(e.unit_id for e in completed),
        "barrier_wait_s": ledger.barrier_wait_s,
    }


def assert_no_barrier_past_timeout(ledger: CohortLedger, *, slack_s: float = 0.0) -> tuple[bool, str]:
    """Check the barrier and every unit stayed within the declared timeout (+ ``slack_s``).

    Returns ``(ok, why)`` rather than raising so a probe can use the coupled runner as a
    both-states control.
    """
    entries = list(ledger.entries)
    if not entries:
        return False, "empty ledger"
    ceiling = max(e.timeout_s for e in entries) + slack_s
    if ledger.barrier_wait_s > ceiling:
        return False, (
            f"barrier_wait_s={ledger.barrier_wait_s:.4f} exceeds max declared timeout+slack {ceiling:.4f}"
        )
    late = [e.unit_id for e in entries if e.duration_s > e.timeout_s + slack_s]
    if late:
        return False, f"units held past their timeout: {late[:5]}"
    return True, f"barrier_wait_s={ledger.barrier_wait_s:.4f} <= {ceiling:.4f}"


def loop_result_to_dict(result: LoopResult) -> dict:
    return {
        "status": result.status,
        "converged": result.converged,
        "bound": result.bound,
        "final_state": dict(result.final_state),
        "iterations": [
            {
                "index": rec.index,
                "predicate_verdict": rec.predicate_verdict,
                "predicate_inputs": rec.predicate_inputs,
                "state": rec.state,
            }
            for rec in result.iterations
        ],
    }
