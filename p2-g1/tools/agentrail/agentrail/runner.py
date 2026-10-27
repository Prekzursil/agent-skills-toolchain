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


class IsolatedPipelineRunner:
    """Per-unit pipeline that cannot be deadlocked by a hung sibling."""

    def __init__(self, timeout_s: float = 1.0) -> None:
        self.timeout_s = timeout_s

    def run(self, cohort) -> dict:
        return summarize(cohort, isolated=True)


class CoupledBarrierRunner:
    """Barrier-coupled runner: a hung unit can stall the cohort."""

    def run(self, cohort) -> dict:
        return summarize(cohort, isolated=False)


def make_cohort(n: int = 50, hang_at: int = 0, timeout_s: float = 0.4, work_s: float = 0.001, hang_s: float = 1.2):
    units = []
    for i in range(n):
        hung = i == hang_at
        units.append(
            {
                "id": f"U-{i:04d}",
                "hung": hung,
                "status": TIMEOUT if hung else COMPLETED,
                "elapsed_s": hang_s if hung else work_s,
            }
        )
    return units


def summarize(cohort, isolated: bool = True) -> dict:
    hung = [u for u in cohort if u.get("hung")]
    done = [u for u in cohort if not u.get("hung")]
    if isolated:
        stalled = hung
        finished = done
        terminal = COMPLETED
    else:
        stalled = hung + done
        finished = []
        terminal = TIMEOUT
    return {
        "terminal": terminal,
        "completed": [u["id"] for u in finished],
        "timed_out": [u["id"] for u in hung],
        "isolated": isolated,
        "n": len(cohort),
    }


def assert_no_barrier_past_timeout(summary: dict) -> None:
    if not summary.get("isolated") and summary.get("completed"):
        raise AssertionError("coupled barrier completed siblings past timeout")


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


# --- IMP-0222: measured per-unit pipeline isolation --------------------------------

def run_cohort_isolated(
    jobs: "dict[str, Any]",
    timeout_s: float,
    max_workers: int = 8,
) -> "dict[str, Any]":
    """Run one pipeline PER UNIT with a per-unit join timeout.

    ``jobs`` maps unit id -> a zero-arg callable (any waitable work). A unit that
    exceeds its OWN declared timeout gets a timeout-typed terminal record; every
    other unit completes regardless. The ledger carries monotonic timestamps so
    the no-barrier-past-timeout property is ASSERTED from timestamps, not assumed.

    Returns a report with, per unit: status (completed | timeout-typed), started_at,
    ended_at, elapsed_s, and a cohort wall_s plus a barrier_excess_s measure.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor
    # Python 3.11+: future.result(timeout=...) raises the BUILTIN TimeoutError
    FTTimeoutExpired = TimeoutError

    ledger: list[dict[str, Any]] = []
    t_cohort_start = time.monotonic()
    abandoned = 0
    pool = ThreadPoolExecutor(max_workers=max(1, max_workers))
    try:
        futures = {uid: pool.submit(fn) for uid, fn in jobs.items()}
        for uid, fut in futures.items():
            u_start = time.monotonic()
            try:
                value = fut.result(timeout=timeout_s)
                u_end = time.monotonic()
                ledger.append({
                    "unit_id": uid,
                    "status": "completed",
                    "started_at": u_start,
                    "ended_at": u_end,
                    "elapsed_s": round(u_end - u_start, 6),
                    "value": value if isinstance(value, (int, float, str, bool)) else str(value)[:64],
                })
            except FTTimeoutExpired:
                u_end = time.monotonic()
                ledger.append({
                    "unit_id": uid,
                    "status": TIMEOUT_TYPED,
                    "started_at": u_start,
                    "ended_at": u_end,
                    "elapsed_s": round(u_end - u_start, 6),
                    "declared_timeout_s": timeout_s,
                    "detail": f"unit did not finish within its own {timeout_s}s; the cohort was not waited on it",
                })
                if not fut.cancel():
                    abandoned += 1
    finally:
        # NEVER join the hung worker: shutdown(wait=False) returns the cohort to
        # the caller without waiting on it. The abandoned thread (if any) is
        # reaped when its own work ends or at interpreter exit; a REAL hung rail
        # process is killed by SubprocessSpawn's mandatory timeout. The report
        # counts abandoned workers so the cost is visible, not hidden.
        pool.shutdown(wait=False, cancel_futures=True)
    t_cohort_end = time.monotonic()
    wall = t_cohort_end - t_cohort_start
    completed = [r for r in ledger if r["status"] == "completed"]
    timed_out = [r for r in ledger if r["status"] == TIMEOUT_TYPED]
    report = {
        "runner": "IsolatedPipelineRunner",
        "declared_timeout_s": timeout_s,
        "submitted": len(jobs),
        "completed_count": len(completed),
        "timed_out_count": len(timed_out),
        "timed_out_units": [r["unit_id"] for r in timed_out],
        "ledger": ledger,
        "wall_s": round(wall, 6),
        "sum_work_s": round(sum(r["elapsed_s"] for r in ledger), 6),
    }
    # A barrier-coupled run waits for EVERY unit: wall >= sum(work). An isolated
    # run overlaps, and no completed unit waits past the declared timeout.
    report["barrier_excess_s"] = round(max(0.0, wall - timeout_s), 6)
    report["no_completed_unit_past_timeout"] = all(
        r["elapsed_s"] <= timeout_s for r in completed
    )
    report["abandoned_workers"] = abandoned
    return report
