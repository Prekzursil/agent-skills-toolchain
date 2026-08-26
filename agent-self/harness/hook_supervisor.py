from __future__ import annotations

import json
import math
import multiprocessing as mp
import os
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from importlib import import_module
from multiprocessing.connection import Connection
from collections.abc import Mapping
from typing import Any, Literal

if os.name == "nt":  # pragma: no cover
    import ctypes
    from ctypes import wintypes


JSONValue = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
WorkerOutcome = Literal["ok", "error", "timeout", "supervisor_error"]

_DEFAULT_STARTUP_TIMEOUT_SECONDS = 5.0
_DEFAULT_EXIT_TIMEOUT_SECONDS = 1.0
_EXITCODE_GRACE_SECONDS = 0.1
_FRAME_MAX_BYTES = 1_048_576
_POLL_INTERVAL_SECONDS = 0.01


@dataclass(frozen=True)
class HookWorkerCall:
    module: str
    function: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    extra_sys_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class HookWorkerResult:
    outcome: WorkerOutcome
    value: JSONValue | None = None
    error: dict[str, JSONValue] | None = None
    elapsed_ms: int = 0
    pid: int | None = None


@dataclass(frozen=True)
class _CleanupStatus:
    verified: bool
    reason: str | None = None


class _MessageTimeout(TimeoutError):
    def __init__(self, stage: str):
        super().__init__(stage)
        self.stage = stage


class _WorkerExited(RuntimeError):
    def __init__(self, stage: str, exitcode: int | None, message: str):
        super().__init__(message)
        self.stage = stage
        self.exitcode = exitcode
        self.message = message


class _ProtocolViolation(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.message = message


def run_isolated(
    call: HookWorkerCall,
    *,
    timeout_seconds: float,
    startup_timeout_seconds: float = _DEFAULT_STARTUP_TIMEOUT_SECONDS,
    exit_timeout_seconds: float = _DEFAULT_EXIT_TIMEOUT_SECONDS,
) -> HookWorkerResult:
    _validate_timeout(timeout_seconds, name="timeout_seconds")
    _validate_timeout(startup_timeout_seconds, name="startup_timeout_seconds")
    _validate_timeout(exit_timeout_seconds, name="exit_timeout_seconds")

    started_at = time.monotonic()
    startup_deadline = _checked_deadline(
        started_at,
        startup_timeout_seconds,
        name="startup_deadline",
    )
    run_deadline = _checked_deadline(
        startup_deadline,
        timeout_seconds,
        name="run_deadline",
    )
    overall_deadline = _checked_deadline(
        run_deadline,
        exit_timeout_seconds,
        name="overall_deadline",
    )

    # Cap serialized input before Windows spawn pickling begins. This bounds the
    # startup payload, but interpreter startup itself still relies on the shared
    # end-to-end deadline enforced by the handshake, run, and cleanup phases.
    try:
        payload_frame = _encode_json_frame(_normalize_call(call))
    except Exception as exc:
        return _supervisor_result(
            started_at,
            pid=None,
            type_name=exc.__class__.__name__,
            message=str(exc),
            stage="startup",
        )

    result_reader: Connection | None = None
    result_writer: Connection | None = None
    control_parent: Connection | None = None
    control_child: Connection | None = None
    process: mp.Process | None = None
    process_started = False
    isolation: _IsolationHandle | None = None
    ready_pid: int | None = None

    def _finish(result: HookWorkerResult) -> HookWorkerResult:
        nonlocal process, isolation
        finalized = _cleanup_and_return(
            result,
            process=process,
            started=process_started,
            isolation=isolation,
            deadline=overall_deadline,
        )
        process = None
        isolation = None
        return finalized

    try:
        try:
            context = mp.get_context("spawn")
            result_reader, result_writer = context.Pipe(duplex=False)
            control_parent, control_child = context.Pipe()
            process = context.Process(
                target=_child_entrypoint,
                args=(
                    payload_frame,
                    result_writer,
                    control_child,
                    startup_timeout_seconds,
                ),
                daemon=False,
            )
        except Exception as exc:
            return _finish(
                _supervisor_result(
                    started_at,
                    pid=None,
                    type_name=exc.__class__.__name__,
                    message=str(exc),
                    stage="startup",
                )
            )

        try:
            process.start()
            process_started = True
        except Exception as exc:
            return _finish(
                _supervisor_result(
                    started_at,
                    pid=None,
                    type_name=exc.__class__.__name__,
                    message=str(exc),
                    stage="startup",
                )
            )
        if _deadline_expired(overall_deadline):
            return _finish(
                _supervisor_result(
                    started_at,
                    pid=process.pid,
                    type_name="TimeoutError",
                    message="shared deadline expired immediately after process start",
                    stage="startup",
                    exitcode=_current_exitcode(process, started=process_started),
                )
            )

        _safe_close_connection(result_writer)
        result_writer = None
        _safe_close_connection(control_child)
        control_child = None

        try:
            ready = _receive_frame_until(
                control_parent,
                process,
                started=True,
                deadline=startup_deadline,
                stage="startup",
            )
        except _MessageTimeout:
            _best_effort_stop_process(
                process, started=process_started, deadline=overall_deadline
            )
            return _finish(
                _supervisor_result(
                    started_at,
                    pid=process.pid,
                    type_name="TimeoutError",
                    message="worker did not complete startup before the deadline",
                    stage="startup",
                )
            )
        except _WorkerExited as exc:
            return _finish(
                _supervisor_result(
                    started_at,
                    pid=process.pid,
                    type_name="WorkerExitError",
                    message=exc.message,
                    stage=exc.stage,
                    exitcode=exc.exitcode,
                )
            )
        except _ProtocolViolation as exc:
            _best_effort_stop_process(
                process, started=process_started, deadline=overall_deadline
            )
            return _finish(
                _supervisor_result(
                    started_at,
                    pid=process.pid,
                    type_name="ProtocolError",
                    message=exc.message,
                    stage=exc.stage,
                )
            )

        if ready.get("kind") != "ready":
            _best_effort_stop_process(
                process, started=process_started, deadline=overall_deadline
            )
            return _finish(
                _supervisor_result(
                    started_at,
                    pid=process.pid,
                    type_name="ProtocolError",
                    message=f"unexpected startup handshake: {ready!r}",
                    stage="startup",
                )
            )

        try:
            ready_pid = _coerce_ready_pid(ready, process.pid)
        except _ProtocolViolation as exc:
            return _finish(
                _supervisor_result(
                    started_at,
                    pid=process.pid,
                    type_name="ProtocolError",
                    message=exc.message,
                    stage=exc.stage,
                    exitcode=_current_exitcode(process, started=process_started),
                )
            )
        try:
            isolation = _create_isolation(ready_pid)
        except Exception as exc:
            _best_effort_stop_process(
                process, started=process_started, deadline=overall_deadline
            )
            return _finish(
                _supervisor_result(
                    started_at,
                    pid=ready_pid,
                    type_name=exc.__class__.__name__,
                    message=str(exc),
                    stage="startup",
                    exitcode=_current_exitcode(process, started=process_started),
                )
            )
        if _deadline_expired(overall_deadline):
            return _finish(
                _finalize_operational_failure(
                    started_at,
                    isolation,
                    process,
                    pid=ready_pid,
                    started=process_started,
                    cleanup_deadline=overall_deadline,
                    type_name="TimeoutError",
                    message="shared deadline expired before the start command could be sent",
                    stage="startup",
                    exitcode=_current_exitcode(process, started=process_started),
                )
            )

        try:
            _send_json_frame(control_parent, {"kind": "start"})
        except Exception as exc:
            return _finish(
                _finalize_operational_failure(
                    started_at,
                    isolation,
                    process,
                    pid=ready_pid,
                    started=process_started,
                    cleanup_deadline=overall_deadline,
                    type_name=exc.__class__.__name__,
                    message=str(exc),
                    stage="run",
                    exitcode=_current_exitcode(process, started=process_started),
                )
            )

        try:
            run_phase_deadline = min(
                _checked_deadline(
                    time.monotonic(),
                    timeout_seconds,
                    name="run_phase_deadline",
                ),
                overall_deadline,
            )
            payload_message = _receive_frame_until(
                result_reader,
                process,
                started=True,
                deadline=run_phase_deadline,
                stage="run",
            )
        except _MessageTimeout:
            return _finish(
                _finalize_timeout_after_start(
                    started_at,
                    isolation,
                    process,
                    pid=ready_pid,
                    started=process_started,
                    timeout_seconds=timeout_seconds,
                    cleanup_deadline=overall_deadline,
                )
            )
        except _WorkerExited as exc:
            return _finish(
                _finalize_operational_failure(
                    started_at,
                    isolation,
                    process,
                    pid=ready_pid,
                    started=process_started,
                    cleanup_deadline=overall_deadline,
                    type_name="WorkerExitError",
                    message=exc.message,
                    stage=exc.stage,
                    exitcode=exc.exitcode,
                )
            )
        except _ProtocolViolation as exc:
            return _finish(
                _finalize_operational_failure(
                    started_at,
                    isolation,
                    process,
                    pid=ready_pid,
                    started=process_started,
                    cleanup_deadline=overall_deadline,
                    type_name="ProtocolError",
                    message=exc.message,
                    stage=exc.stage,
                    exitcode=_current_exitcode(process, started=process_started),
                )
            )

        kind = payload_message.get("kind")
        if kind not in {"ok", "error", "supervisor_error"}:
            return _finish(
                _finalize_operational_failure(
                    started_at,
                    isolation,
                    process,
                    pid=ready_pid,
                    started=process_started,
                    cleanup_deadline=overall_deadline,
                    type_name="ProtocolError",
                    message=f"unexpected child payload kind: {kind!r}",
                    stage="run",
                    exitcode=_current_exitcode(process, started=process_started),
                )
            )

        if not _wait_for_process_exit(
            process, started=process_started, deadline=overall_deadline
        ):
            return _finish(
                _finalize_operational_failure(
                    started_at,
                    isolation,
                    process,
                    pid=ready_pid,
                    started=process_started,
                    cleanup_deadline=overall_deadline,
                    type_name="WorkerLingerError",
                    message="worker returned a payload but remained alive past the join deadline",
                    stage="shutdown",
                    exitcode=_current_exitcode(process, started=process_started),
                )
            )

        cleanup = _call_isolation_status(
            isolation.verify_quiescent,
            operation="verify_quiescent",
            process=process,
            started=process_started,
            deadline=overall_deadline,
        )
        if not cleanup.verified:
            return _finish(
                _supervisor_result(
                    started_at,
                    pid=ready_pid,
                    type_name="CleanupUnverified",
                    message="worker returned a payload but quiescence could not be proven",
                    stage="cleanup",
                    exitcode=_current_exitcode(process, started=process_started),
                    cleanup_status=cleanup,
                )
            )

        return _finish(
            _result_from_child_message(
                payload_message,
                elapsed_ms=_elapsed_ms(started_at),
                pid=ready_pid,
            )
        )
    finally:
        _safe_close_connection(result_reader)
        _safe_close_connection(result_writer)
        _safe_close_connection(control_parent)
        _safe_close_connection(control_child)
        if isolation is not None:
            try:
                isolation.close()
            except Exception:
                pass


def _validate_timeout(value: float, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a finite positive number")
    if not math.isfinite(float(value)) or float(value) <= 0:
        raise ValueError(f"{name} must be a finite positive number")


def _checked_deadline(base: float, delta: float, *, name: str) -> float:
    deadline = base + float(delta)
    if not math.isfinite(deadline):
        raise ValueError(f"{name} overflowed the shared deadline")
    return deadline


def _deadline_expired(deadline: float) -> bool:
    return time.monotonic() >= deadline


def _remaining_seconds(deadline: float) -> float:
    return max(deadline - time.monotonic(), 0.0)


def _coerce_ready_pid(
    ready: Mapping[str, object],
    expected_pid: int | None,
) -> int:
    if "pid" not in ready:
        raise _ProtocolViolation("startup", "startup handshake missing pid")

    raw_pid = ready["pid"]
    if type(raw_pid) is not int:
        raise _ProtocolViolation(
            "startup",
            f"startup handshake pid must be an exact JSON int: {raw_pid!r}",
        )

    pid = raw_pid
    if pid <= 0:
        raise _ProtocolViolation(
            "startup",
            f"startup handshake pid must be positive: {pid!r}",
        )
    if expected_pid is not None and pid != expected_pid:
        raise _ProtocolViolation(
            "startup",
            f"startup handshake pid mismatch: expected {expected_pid}, got {pid}",
        )
    return pid


def _result_from_child_message(
    payload: dict[str, JSONValue], *, elapsed_ms: int, pid: int | None
) -> HookWorkerResult:
    kind = payload.get("kind")
    if kind == "ok":
        return HookWorkerResult(
            outcome="ok",
            value=payload.get("value"),
            elapsed_ms=elapsed_ms,
            pid=pid,
        )
    if kind == "error":
        return HookWorkerResult(
            outcome="error",
            error=_coerce_error(payload.get("error")),
            elapsed_ms=elapsed_ms,
            pid=pid,
        )
    return HookWorkerResult(
        outcome="supervisor_error",
        error=_coerce_error(payload.get("error")),
        elapsed_ms=elapsed_ms,
        pid=pid,
    )


def _coerce_error(value: JSONValue | None) -> dict[str, JSONValue]:
    if isinstance(value, dict):
        return value
    return {"type": "ProtocolError", "message": f"invalid error payload: {value!r}"}


def _supervisor_result(
    started_at: float,
    *,
    pid: int | None,
    type_name: str,
    message: str,
    stage: str,
    exitcode: int | None = None,
    cleanup_status: _CleanupStatus | None = None,
) -> HookWorkerResult:
    return HookWorkerResult(
        outcome="supervisor_error",
        error=_build_error(
            type_name,
            message,
            stage,
            exitcode=exitcode,
            cleanup_status=cleanup_status,
        ),
        elapsed_ms=_elapsed_ms(started_at),
        pid=pid,
    )


def _timeout_result(
    started_at: float,
    *,
    pid: int | None,
    timeout_seconds: float,
    cleanup_status: _CleanupStatus,
) -> HookWorkerResult:
    if cleanup_status.verified:
        return HookWorkerResult(
            outcome="timeout",
            error=_build_error(
                "TimeoutError",
                f"worker exceeded timeout of {timeout_seconds:.3f}s",
                "run",
            ),
            elapsed_ms=_elapsed_ms(started_at),
            pid=pid,
        )
    return HookWorkerResult(
        outcome="supervisor_error",
        error=_build_error(
            "TimeoutError",
            f"worker exceeded timeout of {timeout_seconds:.3f}s",
            "run",
            cleanup_status=cleanup_status,
        ),
        elapsed_ms=_elapsed_ms(started_at),
        pid=pid,
    )


def _build_error(
    type_name: str,
    message: str,
    stage: str,
    *,
    exitcode: int | None = None,
    cleanup_status: _CleanupStatus | None = None,
) -> dict[str, JSONValue]:
    payload: dict[str, JSONValue] = {
        "type": type_name,
        "message": message,
        "stage": stage,
    }
    if exitcode is not None:
        payload["exitcode"] = exitcode
    if cleanup_status is not None and not cleanup_status.verified:
        payload["cleanup_unverified"] = True
        if cleanup_status.reason:
            payload["cleanup_error"] = cleanup_status.reason
    return payload


def _call_isolation_status(
    operation_fn,
    *,
    operation: str,
    process: mp.Process,
    started: bool,
    deadline: float,
) -> _CleanupStatus:
    try:
        return operation_fn(process, started=started, deadline=deadline)
    except Exception as exc:
        return _CleanupStatus(
            False,
            f"{operation} raised {exc.__class__.__name__}: {exc}",
        )


def _finalize_operational_failure(
    started_at: float,
    isolation: "_IsolationHandle",
    process: mp.Process,
    *,
    pid: int | None,
    started: bool,
    cleanup_deadline: float,
    type_name: str,
    message: str,
    stage: str,
    exitcode: int | None = None,
) -> HookWorkerResult:
    cleanup = _call_isolation_status(
        isolation.terminate_and_verify,
        operation="terminate_and_verify",
        process=process,
        started=started,
        deadline=cleanup_deadline,
    )
    return _supervisor_result(
        started_at,
        pid=pid,
        type_name=type_name,
        message=message,
        stage=stage,
        exitcode=exitcode,
        cleanup_status=cleanup,
    )


def _finalize_timeout_after_start(
    started_at: float,
    isolation: "_IsolationHandle",
    process: mp.Process,
    *,
    pid: int | None,
    started: bool,
    timeout_seconds: float,
    cleanup_deadline: float,
) -> HookWorkerResult:
    cleanup = _call_isolation_status(
        isolation.terminate_and_verify,
        operation="terminate_and_verify",
        process=process,
        started=started,
        deadline=cleanup_deadline,
    )
    return _timeout_result(
        started_at,
        pid=pid,
        timeout_seconds=timeout_seconds,
        cleanup_status=cleanup,
    )


def _elapsed_ms(started_at: float) -> int:
    return int((time.monotonic() - started_at) * 1000)


def _normalize_call(call: HookWorkerCall) -> dict[str, JSONValue]:
    module = str(call.module).strip()
    function = str(call.function).strip()
    if not module:
        raise ValueError("call.module must be non-empty")
    if not function:
        raise ValueError("call.function must be non-empty")
    args = _normalize_json(list(call.args), context="call.args")
    kwargs = _normalize_json(call.kwargs, context="call.kwargs")
    extra_paths = _normalize_json(
        list(call.extra_sys_paths), context="call.extra_sys_paths"
    )
    assert isinstance(args, list)
    assert isinstance(kwargs, dict)
    assert isinstance(extra_paths, list)
    return {
        "module": module,
        "function": function,
        "args": args,
        "kwargs": kwargs,
        "extra_sys_paths": [str(item) for item in extra_paths],
    }


def _normalize_json(value: Any, *, context: str) -> JSONValue:
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError) as exc:  # pragma: no cover
        raise ValueError(f"{context} must be JSON-serializable") from exc


def _child_entrypoint(
    payload_frame: bytes,
    result_writer: Connection,
    control_channel: Connection,
    startup_timeout_seconds: float,
) -> None:
    try:
        if os.name != "nt":
            os.setsid()
        payload = _decode_json_frame(payload_frame, stage="startup")
        _send_json_frame(control_channel, {"kind": "ready", "pid": os.getpid()})
        if not control_channel.poll(startup_timeout_seconds):
            return
        command = _recv_json_frame(control_channel, stage="startup")
        if command.get("kind") != "start":
            _send_json_frame(
                result_writer,
                {
                    "kind": "supervisor_error",
                    "error": {
                        "type": "ProtocolError",
                        "message": f"unexpected start command: {command!r}",
                    },
                },
            )
            return
        _send_json_frame(result_writer, _invoke_target(payload))
    except BaseException as exc:  # pragma: no cover
        try:
            _send_json_frame(
                result_writer,
                {"kind": "supervisor_error", "error": _serialize_exception(exc)},
            )
        except Exception:
            pass
    finally:
        _safe_close_connection(result_writer)
        _safe_close_connection(control_channel)


def _invoke_target(payload: dict[str, JSONValue]) -> dict[str, JSONValue]:
    extra_paths = payload.get("extra_sys_paths")
    if isinstance(extra_paths, list):
        for entry in reversed(extra_paths):
            path_entry = str(entry)
            if path_entry and path_entry not in sys.path:
                sys.path.insert(0, path_entry)
    try:
        module = import_module(str(payload["module"]))
        target = getattr(module, str(payload["function"]))
        if not callable(target):
            raise TypeError(
                f"resolved target {payload['module']}.{payload['function']} is not callable"
            )
        raw_value = target(*list(payload["args"]), **dict(payload["kwargs"]))
        return {
            "kind": "ok",
            "value": _normalize_json(raw_value, context="return value"),
        }
    except Exception as exc:
        return {"kind": "error", "error": _serialize_exception(exc)}


def _serialize_exception(exc: BaseException) -> dict[str, JSONValue]:
    return {
        "type": exc.__class__.__name__,
        "message": str(exc),
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }


def _receive_frame_until(
    connection: Connection,
    process: mp.Process,
    *,
    started: bool,
    deadline: float,
    stage: str,
) -> dict[str, JSONValue]:
    while True:
        exitcode = _current_exitcode(process, started=started)
        if exitcode is None and _process_is_definitely_dead(process):
            raise _WorkerExited(
                stage,
                _exitcode_with_grace(
                    process,
                    started=started,
                    timeout_seconds=_EXITCODE_GRACE_SECONDS,
                ),
                f"worker exited before sending a {stage} frame",
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if exitcode is not None:
                raise _WorkerExited(
                    stage,
                    exitcode,
                    f"worker exited before sending a complete {stage} frame",
                )
            raise _MessageTimeout(stage)
        try:
            has_data = connection.poll(min(remaining, _POLL_INTERVAL_SECONDS))
        except (EOFError, OSError, RecursionError, ValueError) as exc:
            exitcode = _exitcode_with_grace(
                process, started=started, timeout_seconds=_EXITCODE_GRACE_SECONDS
            )
            if exitcode is not None:
                raise _WorkerExited(
                    stage,
                    exitcode,
                    f"worker exited before sending a complete {stage} frame",
                ) from exc
            raise _ProtocolViolation(
                stage,
                f"{stage} transport error: {exc.__class__.__name__}: {exc}",
            ) from exc
        if has_data:
            try:
                return _recv_json_frame(connection, stage=stage)
            except EOFError as exc:
                exitcode = _exitcode_with_grace(
                    process, started=started, timeout_seconds=_EXITCODE_GRACE_SECONDS
                )
                if exitcode is not None:
                    raise _WorkerExited(
                        stage,
                        exitcode,
                        f"worker exited before sending a complete {stage} frame",
                    ) from exc
                raise _ProtocolViolation(
                    stage, f"{stage} channel closed before a complete frame arrived"
                ) from exc
            except (OSError, RecursionError, ValueError) as exc:
                exitcode = _exitcode_with_grace(
                    process, started=started, timeout_seconds=_EXITCODE_GRACE_SECONDS
                )
                if exitcode is not None:
                    raise _WorkerExited(
                        stage,
                        exitcode,
                        f"worker exited before sending a valid {stage} frame",
                    ) from exc
                raise _ProtocolViolation(
                    stage,
                    f"{stage} transport error: {exc.__class__.__name__}: {exc}",
                ) from exc
            except _ProtocolViolation as exc:
                exitcode = _exitcode_with_grace(
                    process, started=started, timeout_seconds=_EXITCODE_GRACE_SECONDS
                )
                if exitcode is not None:
                    raise _WorkerExited(
                        stage,
                        exitcode,
                        f"worker exited before sending a valid {stage} frame",
                    ) from exc
                raise
        if exitcode is not None:
            raise _WorkerExited(
                stage, exitcode, f"worker exited before sending a {stage} frame"
            )


def _send_json_frame(connection: Connection, value: dict[str, JSONValue]) -> None:
    connection.send_bytes(_encode_json_frame(value))


def _encode_json_frame(value: dict[str, JSONValue]) -> bytes:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(payload) > _FRAME_MAX_BYTES:
        raise ValueError(f"frame exceeds {_FRAME_MAX_BYTES} bytes")
    return payload


def _decode_json_frame(raw: bytes, *, stage: str) -> dict[str, JSONValue]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _ProtocolViolation(stage, f"{stage} frame is not valid UTF-8") from exc
    try:
        parsed = json.loads(text)
    except RecursionError as exc:
        raise _ProtocolViolation(
            stage,
            f"{stage} frame parsing failed: {exc.__class__.__name__}: {exc}",
        ) from exc
    except json.JSONDecodeError as exc:
        raise _ProtocolViolation(stage, f"{stage} frame is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise _ProtocolViolation(stage, f"{stage} frame must decode to a JSON object")
    return parsed


def _recv_json_frame(connection: Connection, *, stage: str) -> dict[str, JSONValue]:
    try:
        raw = connection.recv_bytes(maxlength=_FRAME_MAX_BYTES)
    except (OSError, RecursionError) as exc:
        raise _ProtocolViolation(
            stage,
            f"{stage} transport error: {exc.__class__.__name__}: {exc}",
        ) from exc
    return _decode_json_frame(raw, stage=stage)


def _current_exitcode(process: mp.Process, *, started: bool) -> int | None:
    if not started:
        return None
    process.join(timeout=0)
    return process.exitcode


def _exitcode_with_grace(
    process: mp.Process, *, started: bool, timeout_seconds: float
) -> int | None:
    if not started:
        return None
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        exitcode = _current_exitcode(process, started=started)
        if exitcode is not None:
            return exitcode
        time.sleep(_POLL_INTERVAL_SECONDS)
    return _current_exitcode(process, started=started)


def _wait_for_process_exit(
    process: mp.Process, *, started: bool, deadline: float
) -> bool:
    if not started:
        return True
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        process.join(timeout=min(_POLL_INTERVAL_SECONDS, max(remaining, 0.0)))
        if process.exitcode is not None:
            return True
    process.join(timeout=0)
    return process.exitcode is not None


def _best_effort_stop_process(
    process: mp.Process | None, *, started: bool, deadline: float
) -> str | None:
    if process is None or not started:
        return None

    exitcode = process.exitcode
    try:
        alive_state = _probe_is_alive(process)
    except (AssertionError, OSError, PermissionError, ValueError) as exc:
        if exitcode is None:
            return (
                "process stop failed during liveness probe: "
                f"{exc.__class__.__name__}: {exc}"
            )
        alive_state = None

    if exitcode is None or alive_state is True:
        try:
            process.kill()
        except (AssertionError, OSError, PermissionError, ValueError) as exc:
            return f"process stop failed during kill: {exc.__class__.__name__}: {exc}"
    try:
        process.join(timeout=_remaining_seconds(deadline))
    except (AssertionError, OSError, PermissionError, ValueError) as exc:
        return f"process stop failed during join: {exc.__class__.__name__}: {exc}"

    if process.exitcode is None:
        return "process stop failed to prove exit before the cleanup deadline"
    try:
        if _probe_is_alive(process) is True:
            return (
                "process stop failed to prove terminal liveness before cleanup return"
            )
    except (AssertionError, OSError, PermissionError, ValueError) as exc:
        return (
            "process stop failed during terminal liveness proof: "
            f"{exc.__class__.__name__}: {exc}"
        )
    return None


def _probe_is_alive(process: mp.Process) -> bool | None:
    alive_probe = getattr(process, "is_alive", None)
    if not callable(alive_probe):
        return None
    return bool(alive_probe())


def _process_is_definitely_dead(process: mp.Process) -> bool:
    try:
        return _probe_is_alive(process) is False
    except (AssertionError, OSError, PermissionError, ValueError):
        return False


def _safe_close_connection(connection: Connection | None) -> None:
    if connection is None:
        return
    try:
        connection.close()
    except OSError:
        return


def _cleanup_and_return(
    result: HookWorkerResult,
    *,
    process: mp.Process | None,
    started: bool,
    isolation: _IsolationHandle | None,
    deadline: float,
) -> HookWorkerResult:
    cleanup_errors: list[str] = []
    stop_error = _best_effort_stop_process(process, started=started, deadline=deadline)
    if stop_error:
        cleanup_errors.append(stop_error)
    if isolation is not None:
        try:
            isolation.close()
        except Exception as exc:
            cleanup_errors.append(
                f"isolation close failed: {exc.__class__.__name__}: {exc}"
            )
    if not cleanup_errors:
        return result
    return _attach_cleanup_failure(result, "; ".join(cleanup_errors))


def _attach_cleanup_failure(
    result: HookWorkerResult, cleanup_error: str
) -> HookWorkerResult:
    error = dict(result.error or {})
    if not error:
        error = {
            "type": "CleanupUnverified",
            "message": "final cleanup failed after the worker completed",
            "stage": "cleanup",
        }
    error["cleanup_unverified"] = True
    error["cleanup_error"] = cleanup_error
    error["original_outcome"] = result.outcome
    if result.outcome == "ok" and result.value is not None:
        error["original_value"] = result.value
    return HookWorkerResult(
        outcome="supervisor_error",
        value=result.value,
        error=error,
        elapsed_ms=result.elapsed_ms,
        pid=result.pid,
    )


class _IsolationHandle:
    def terminate_and_verify(
        self, process: mp.Process, *, started: bool, deadline: float
    ) -> _CleanupStatus:
        raise NotImplementedError

    def verify_quiescent(
        self, process: mp.Process, *, started: bool, deadline: float
    ) -> _CleanupStatus:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


def _create_isolation(pid: int) -> _IsolationHandle:
    if os.name == "nt":
        return _WindowsJobHandle.attach(pid)
    return _UnsupportedPosixIsolation(pgid=pid)


class _UnsupportedPosixIsolation(_IsolationHandle):
    def __init__(self, *, pgid: int) -> None:
        self._pgid = pgid

    def terminate_and_verify(
        self, process: mp.Process, *, started: bool, deadline: float
    ) -> _CleanupStatus:
        try:
            os.killpg(self._pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        _wait_for_process_exit(process, started=started, deadline=deadline)
        return _CleanupStatus(
            False,
            "POSIX verified descendant cleanup is unsupported without cgroup-v2; "
            "process groups cannot prove detached-child termination",
        )

    def verify_quiescent(
        self, process: mp.Process, *, started: bool, deadline: float
    ) -> _CleanupStatus:
        _wait_for_process_exit(process, started=started, deadline=deadline)
        return _CleanupStatus(
            False,
            "POSIX verified descendant cleanup is unsupported without cgroup-v2; "
            "process groups cannot prove detached-child termination",
        )

    def close(self) -> None:
        return None


if os.name == "nt":  # pragma: no cover
    _BOOL = wintypes.BOOL
    _DWORD = wintypes.DWORD
    _HANDLE = wintypes.HANDLE
    _LPVOID = wintypes.LPVOID
    _WAIT_OBJECT_0 = 0x00000000
    _WAIT_TIMEOUT = 0x00000102

    _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _PROCESS_SET_QUOTA = 0x0100
    _PROCESS_TERMINATE = 0x0001
    _SYNCHRONIZE = 0x00100000

    class _LARGE_INTEGER(ctypes.Structure):
        _fields_ = [("QuadPart", ctypes.c_longlong)]

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", _LARGE_INTEGER),
            ("PerJobUserTimeLimit", _LARGE_INTEGER),
            ("LimitFlags", _DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", _DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", _DWORD),
            ("SchedulingClass", _DWORD),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION_STRUCT(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", _LARGE_INTEGER),
            ("TotalKernelTime", _LARGE_INTEGER),
            ("ThisPeriodTotalUserTime", _LARGE_INTEGER),
            ("ThisPeriodTotalKernelTime", _LARGE_INTEGER),
            ("TotalPageFaultCount", _DWORD),
            ("TotalProcesses", _DWORD),
            ("ActiveProcesses", _DWORD),
            ("TotalTerminatedProcesses", _DWORD),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.AssignProcessToJobObject.argtypes = [_HANDLE, _HANDLE]
    _kernel32.AssignProcessToJobObject.restype = _BOOL
    _kernel32.CloseHandle.argtypes = [_HANDLE]
    _kernel32.CloseHandle.restype = _BOOL
    _kernel32.CreateJobObjectW.argtypes = [_LPVOID, wintypes.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = _HANDLE
    _kernel32.OpenProcess.argtypes = [_DWORD, _BOOL, _DWORD]
    _kernel32.OpenProcess.restype = _HANDLE
    _kernel32.QueryInformationJobObject.argtypes = [
        _HANDLE,
        _DWORD,
        _LPVOID,
        _DWORD,
        ctypes.POINTER(_DWORD),
    ]
    _kernel32.QueryInformationJobObject.restype = _BOOL
    _kernel32.SetInformationJobObject.argtypes = [_HANDLE, _DWORD, _LPVOID, _DWORD]
    _kernel32.SetInformationJobObject.restype = _BOOL
    _kernel32.TerminateJobObject.argtypes = [_HANDLE, _DWORD]
    _kernel32.TerminateJobObject.restype = _BOOL
    _kernel32.WaitForSingleObject.argtypes = [_HANDLE, _DWORD]
    _kernel32.WaitForSingleObject.restype = _DWORD

    def _raise_last_winerror(context: str) -> OSError:
        error_code = ctypes.get_last_error()
        raise OSError(error_code, f"{context} failed with winerror={error_code}")

    class _WindowsJobHandle(_IsolationHandle):
        def __init__(self, *, job_handle: int, leader_handle: int) -> None:
            self._job_handle = job_handle
            self._leader_handle = leader_handle

        @classmethod
        def attach(cls, pid: int) -> "_WindowsJobHandle":
            leader_handle = _kernel32.OpenProcess(
                _PROCESS_SET_QUOTA
                | _PROCESS_TERMINATE
                | _PROCESS_QUERY_LIMITED_INFORMATION
                | _SYNCHRONIZE,
                False,
                pid,
            )
            if not leader_handle:
                _raise_last_winerror("OpenProcess")
            job_handle = _kernel32.CreateJobObjectW(None, None)
            if not job_handle:
                close_error = _close_handle_checked(
                    leader_handle, label="leader_handle"
                )
                if close_error:
                    raise OSError(close_error)
                _raise_last_winerror("CreateJobObjectW")
            try:
                limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                limits.BasicLimitInformation.LimitFlags = (
                    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                )
                ok = _kernel32.SetInformationJobObject(
                    job_handle,
                    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                    ctypes.byref(limits),
                    ctypes.sizeof(limits),
                )
                if not ok:
                    _raise_last_winerror("SetInformationJobObject")
                ok = _kernel32.AssignProcessToJobObject(job_handle, leader_handle)
                if not ok:
                    _raise_last_winerror("AssignProcessToJobObject")
            except Exception:
                _close_handle_checked(job_handle, label="job_handle")
                _close_handle_checked(leader_handle, label="leader_handle")
                raise
            return cls(job_handle=int(job_handle), leader_handle=int(leader_handle))

        def terminate_and_verify(
            self, process: mp.Process, *, started: bool, deadline: float
        ) -> _CleanupStatus:
            return self._cleanup(
                process, started=started, deadline=deadline, terminate=True
            )

        def verify_quiescent(
            self, process: mp.Process, *, started: bool, deadline: float
        ) -> _CleanupStatus:
            return self._cleanup(
                process, started=started, deadline=deadline, terminate=False
            )

        def close(self) -> None:
            self._close_handles()

        def _cleanup(
            self,
            process: mp.Process,
            *,
            started: bool,
            deadline: float,
            terminate: bool,
        ) -> _CleanupStatus:
            errors: list[str] = []
            if terminate and self._job_handle:
                ok = _kernel32.TerminateJobObject(self._job_handle, 1)
                if not ok:
                    errors.append(_format_last_winerror("TerminateJobObject"))
            process_stopped = _wait_for_process_exit(
                process, started=started, deadline=deadline
            )
            job_quiescent, reason = self._wait_for_job_quiescent(deadline)
            if reason:
                errors.append(reason)
            errors.extend(self._close_handles())
            if not process_stopped:
                errors.append("leader process did not exit before the cleanup deadline")
            if not job_quiescent:
                errors.append(
                    "job object did not prove zero active processes before the cleanup deadline"
                )
            if errors:
                return _CleanupStatus(False, "; ".join(dict.fromkeys(errors)))
            return _CleanupStatus(True)

        def _wait_for_job_quiescent(self, deadline: float) -> tuple[bool, str | None]:
            if not self._job_handle:
                return False, "job handle was unavailable during cleanup verification"
            while time.monotonic() < deadline:
                wait_result = _kernel32.WaitForSingleObject(self._job_handle, 0)
                active_processes, query_error = self._active_process_count()
                if query_error:
                    return False, query_error
                if wait_result == _WAIT_OBJECT_0 and active_processes == 0:
                    return True, None
                if wait_result not in {_WAIT_OBJECT_0, _WAIT_TIMEOUT}:
                    return (
                        False,
                        f"WaitForSingleObject(job_handle) returned {wait_result}",
                    )
                if active_processes == 0:
                    return True, None
                time.sleep(_POLL_INTERVAL_SECONDS)
            return False, None

        def _active_process_count(self) -> tuple[int | None, str | None]:
            if not self._job_handle:
                return None, "job handle was unavailable during active-process query"
            info = _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION_STRUCT()
            returned = _DWORD()
            ok = _kernel32.QueryInformationJobObject(
                self._job_handle,
                _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
                ctypes.byref(info),
                ctypes.sizeof(info),
                ctypes.byref(returned),
            )
            if not ok:
                return None, _format_last_winerror("QueryInformationJobObject")
            return int(info.ActiveProcesses), None

        def _close_handles(self) -> list[str]:
            errors: list[str] = []
            if self._leader_handle:
                error = _close_handle_checked(
                    self._leader_handle, label="leader_handle"
                )
                if error:
                    errors.append(error)
                self._leader_handle = 0
            if self._job_handle:
                error = _close_handle_checked(self._job_handle, label="job_handle")
                if error:
                    errors.append(error)
                self._job_handle = 0
            return errors

    def _close_handle_checked(handle: int, *, label: str) -> str | None:
        ok = _kernel32.CloseHandle(handle)
        if ok:
            return None
        return _format_last_winerror(f"CloseHandle({label})")

    def _format_last_winerror(context: str) -> str:
        return f"{context} failed with winerror={ctypes.get_last_error()}"
