from __future__ import annotations

import math
import multiprocessing as mp
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from harness import hook_supervisor
from harness.hook_supervisor import (
    _CleanupStatus,
    _FRAME_MAX_BYTES,
    _ProtocolViolation,
    _cleanup_and_return,
    _recv_json_frame,
    HookWorkerCall,
    HookWorkerResult,
    run_isolated,
)


def _write_worker_module(tmp_path: Path) -> tuple[str, str]:
    module_name = "hook_supervisor_fixture_worker"
    module_path = tmp_path / f"{module_name}.py"
    module_path.write_text(
        textwrap.dedent(
            """
            from __future__ import annotations

            import os
            import subprocess
            import sys
            import time
            from pathlib import Path

            _GRANDCHILD = (
                "import sys, time; "
                "from pathlib import Path; "
                "time.sleep(float(sys.argv[2])); "
                "Path(sys.argv[1]).write_text('grandchild', encoding='ascii')"
            )

            _PERSISTENT_CHILD = (
                "import sys\\n"
                "import time\\n"
                "from pathlib import Path\\n"
                "ready = Path(sys.argv[1])\\n"
                "alive = Path(sys.argv[2])\\n"
                "interval = float(sys.argv[3])\\n"
                "ready.write_text('ready', encoding='ascii')\\n"
                "counter = 0\\n"
                "deadline = time.monotonic() + 60.0\\n"
                "while time.monotonic() < deadline:\\n"
                "    alive.write_text(str(counter), encoding='ascii')\\n"
                "    counter += 1\\n"
                "    time.sleep(interval)\\n"
            )


            def fast_value(label: str) -> dict[str, object]:
                return {"echo": label, "ok": True}


            def raise_failure() -> None:
                raise RuntimeError("boom from worker")


            def late_write(child_marker: str, grandchild_marker: str, delay: float) -> dict[str, object]:
                subprocess.Popen(
                    [sys.executable, "-c", _GRANDCHILD, grandchild_marker, str(delay)],
                    close_fds=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(delay)
                Path(child_marker).write_text("child", encoding="ascii")
                return {"unexpected": True}


            def exit_abruptly(exitcode: int) -> None:
                os._exit(exitcode)


            def spawn_child_and_exit_abruptly(marker: str, delay: float, detached: bool = False) -> None:
                kwargs = {
                    "close_fds": True,
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.DEVNULL,
                }
                if detached and os.name != "nt":
                    kwargs["start_new_session"] = True
                subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        "import sys, time; from pathlib import Path; time.sleep(float(sys.argv[2])); Path(sys.argv[1]).write_text('child', encoding='ascii')",
                        marker,
                        str(delay),
                    ],
                    **kwargs,
                )
                os._exit(9)


            def oversized_value(size: int) -> dict[str, object]:
                return {"blob": "x" * size}


            def persistent_descendant(ready_marker: str, alive_marker: str, delay: float) -> None:
                subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        _PERSISTENT_CHILD,
                        ready_marker,
                        alive_marker,
                        str(delay),
                    ],
                    close_fds=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                ready = Path(ready_marker)
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    if ready.exists():
                        break
                    time.sleep(0.01)
                else:
                    raise TimeoutError("persistent descendant did not signal readiness")
                time.sleep(10.0)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return module_name, str(tmp_path)


def _wait_for_file(path: Path, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for {path}")


def _assert_process_terminated_windows(pid: int, timeout: float = 1.0) -> None:
    if os.name != "nt":
        return

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        handle = hook_supervisor._kernel32.OpenProcess(
            hook_supervisor._SYNCHRONIZE,
            False,
            pid,
        )
        if not handle:
            return
        try:
            state = hook_supervisor._kernel32.WaitForSingleObject(handle, 0)
            if state == hook_supervisor._WAIT_OBJECT_0:
                return
            if state != hook_supervisor._WAIT_TIMEOUT:
                raise AssertionError(f"unexpected wait state for pid {pid}: {state}")
        finally:
            hook_supervisor._kernel32.CloseHandle(handle)
        time.sleep(0.01)
    raise AssertionError(f"worker pid {pid} remained live after supervisor return")


@pytest.mark.skipif(
    os.name != "nt", reason="verified end-to-end cleanup path is Windows-only"
)
def test_run_isolated_returns_fast_json_value(tmp_path):
    module_name, extra_path = _write_worker_module(tmp_path)

    result = run_isolated(
        HookWorkerCall(
            module=module_name,
            function="fast_value",
            args=("alpha",),
            extra_sys_paths=(extra_path,),
        ),
        timeout_seconds=2.0,
    )

    assert result.outcome == "ok"
    assert result.value == {"echo": "alpha", "ok": True}
    assert result.error is None
    assert result.pid is not None
    assert result.elapsed_ms < 6000


@pytest.mark.skipif(
    os.name != "nt", reason="verified end-to-end cleanup path is Windows-only"
)
def test_run_isolated_returns_structured_exception(tmp_path):
    module_name, extra_path = _write_worker_module(tmp_path)

    result = run_isolated(
        HookWorkerCall(
            module=module_name,
            function="raise_failure",
            extra_sys_paths=(extra_path,),
        ),
        timeout_seconds=2.0,
    )

    assert result.outcome == "error"
    assert result.value is None
    assert result.error is not None
    assert result.error["type"] == "RuntimeError"
    assert result.error["message"] == "boom from worker"
    assert "raise_failure" in str(result.error["traceback"])
    assert result.pid is not None


@pytest.mark.skipif(
    os.name != "nt", reason="verified timeout containment path is Windows-only"
)
def test_run_isolated_timeout_kills_child_and_grandchild(tmp_path):
    module_name, extra_path = _write_worker_module(tmp_path)
    child_marker = tmp_path / "child.txt"
    grandchild_marker = tmp_path / "grandchild.txt"
    delay = 0.35

    result = run_isolated(
        HookWorkerCall(
            module=module_name,
            function="late_write",
            args=(str(child_marker), str(grandchild_marker), delay),
            extra_sys_paths=(extra_path,),
        ),
        timeout_seconds=0.1,
        exit_timeout_seconds=2.0,
    )

    assert result.outcome in {"timeout", "supervisor_error"}
    assert result.value is None
    assert result.error is not None
    assert result.error["type"] == "TimeoutError"
    if result.outcome == "supervisor_error":
        assert result.error["cleanup_unverified"] is True
    assert child_marker.exists() is False
    assert grandchild_marker.exists() is False
    time.sleep(delay)
    assert child_marker.exists() is False
    assert grandchild_marker.exists() is False
    time.sleep(delay)
    assert child_marker.exists() is False
    assert grandchild_marker.exists() is False
    assert result.elapsed_ms < 4000


@pytest.mark.skipif(
    os.name != "nt", reason="verified abrupt-exit cleanup path is Windows-only"
)
def test_run_isolated_reports_abrupt_worker_exit_with_exitcode(tmp_path):
    module_name, extra_path = _write_worker_module(tmp_path)

    result = run_isolated(
        HookWorkerCall(
            module=module_name,
            function="exit_abruptly",
            args=(17,),
            extra_sys_paths=(extra_path,),
        ),
        timeout_seconds=1.0,
        exit_timeout_seconds=2.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["type"] == "WorkerExitError"
    assert result.error["stage"] == "run"
    assert result.error["exitcode"] == 17
    assert result.error.get("cleanup_unverified") is not True


@pytest.mark.skipif(
    os.name != "nt", reason="verified abrupt-exit cleanup path is Windows-only"
)
def test_run_isolated_cleans_descendants_after_operational_failure(tmp_path):
    module_name, extra_path = _write_worker_module(tmp_path)
    marker = tmp_path / "abrupt-child.txt"
    delay = 0.25

    result = run_isolated(
        HookWorkerCall(
            module=module_name,
            function="spawn_child_and_exit_abruptly",
            args=(str(marker), delay),
            extra_sys_paths=(extra_path,),
        ),
        timeout_seconds=2.0,
        exit_timeout_seconds=2.0,
    )

    assert result.outcome in {"supervisor_error", "timeout"}
    assert result.error is not None
    assert result.error["type"] in {"WorkerExitError", "TimeoutError"}
    if result.outcome == "supervisor_error":
        assert result.error.get("cleanup_unverified") is not True
    assert marker.exists() is False
    time.sleep(delay)
    assert marker.exists() is False
    time.sleep(delay)
    assert marker.exists() is False


@pytest.mark.skipif(
    os.name != "nt", reason="verified timeout containment path is Windows-only"
)
def test_run_isolated_kills_persistent_descendant_activity(tmp_path):
    module_name, extra_path = _write_worker_module(tmp_path)
    baseline_ready = tmp_path / "baseline-ready.txt"
    baseline_alive = tmp_path / "baseline-alive.txt"
    ready_marker = tmp_path / "persistent-ready.txt"
    alive_marker = tmp_path / "persistent-alive.txt"
    delay = 0.05
    baseline = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import sys\n"
                "import time\n"
                "from pathlib import Path\n"
                "ready = Path(sys.argv[1])\n"
                "alive = Path(sys.argv[2])\n"
                "ready.write_text('ready', encoding='ascii')\n"
                "alive.write_text('0', encoding='ascii')\n"
                "time.sleep(60.0)\n"
            ),
            str(baseline_ready),
            str(baseline_alive),
        ],
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_file(baseline_ready, timeout=2.0)
        _wait_for_file(baseline_alive, timeout=2.0)
    finally:
        baseline.terminate()
        baseline.wait(timeout=5)

    result = run_isolated(
        HookWorkerCall(
            module=module_name,
            function="persistent_descendant",
            args=(str(ready_marker), str(alive_marker), delay),
            extra_sys_paths=(extra_path,),
        ),
        timeout_seconds=1.0,
        exit_timeout_seconds=2.0,
    )

    assert result.outcome == "timeout"
    ready_exists = ready_marker.exists()
    alive_exists = alive_marker.exists()
    first_content = alive_marker.read_text(encoding="ascii") if alive_exists else None
    time.sleep(delay * 3)
    assert ready_marker.exists() is ready_exists
    assert alive_marker.exists() is alive_exists
    second_content = alive_marker.read_text(encoding="ascii") if alive_exists else None
    time.sleep(delay * 3)
    assert ready_marker.exists() is ready_exists
    assert alive_marker.exists() is alive_exists
    third_content = alive_marker.read_text(encoding="ascii") if alive_exists else None
    assert first_content == second_content == third_content
    assert result.pid is not None
    _assert_process_terminated_windows(result.pid)


@pytest.mark.skipif(
    os.name != "nt", reason="verified end-to-end cleanup path is Windows-only"
)
def test_run_isolated_supports_repeated_calls_without_leaking_state(tmp_path):
    module_name, extra_path = _write_worker_module(tmp_path)

    for label in ["one", "two", "three"]:
        result = run_isolated(
            HookWorkerCall(
                module=module_name,
                function="fast_value",
                args=(label,),
                extra_sys_paths=(extra_path,),
            ),
            timeout_seconds=2.0,
        )
        assert result.outcome == "ok"
        assert result.value == {"echo": label, "ok": True}


def test_run_isolated_rejects_nonfinite_and_nonpositive_timeouts():
    call = HookWorkerCall(module="m", function="f")
    for bad in [0, -1, math.nan, math.inf, -math.inf]:
        with pytest.raises(ValueError, match="finite positive number"):
            run_isolated(call, timeout_seconds=bad)
        with pytest.raises(ValueError, match="finite positive number"):
            run_isolated(call, timeout_seconds=1.0, startup_timeout_seconds=bad)
        with pytest.raises(ValueError, match="finite positive number"):
            run_isolated(call, timeout_seconds=1.0, exit_timeout_seconds=bad)


def test_run_isolated_rejects_oversized_input_before_process_start(monkeypatch):
    started = {"value": False}

    class FakeConnection:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def send_bytes(self, payload: bytes) -> None:
            return None

    class FakeProcess:
        pid = None
        exitcode = None

        def start(self) -> None:
            started["value"] = True
            raise AssertionError("start should not run for oversized input")

        def join(self, timeout: float = 0) -> None:
            raise AssertionError("join must not be called on unstarted process")

        def kill(self) -> None:
            raise AssertionError("kill must not be called on unstarted process")

        def is_alive(self) -> bool:
            raise AssertionError("is_alive must not be called on unstarted process")

    pipes: list[FakeConnection] = []

    class FakeContext:
        def Pipe(self, duplex: bool = False) -> tuple[FakeConnection, FakeConnection]:
            left = FakeConnection()
            right = FakeConnection()
            pipes.extend([left, right])
            return left, right

        def Process(self, **_: object) -> FakeProcess:
            return FakeProcess()

    monkeypatch.setattr(hook_supervisor.mp, "get_context", lambda _name: FakeContext())
    huge_arg = "x" * _FRAME_MAX_BYTES
    result = run_isolated(
        HookWorkerCall(module="fixture", function="worker", args=(huge_arg,)),
        timeout_seconds=1.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["type"] == "ValueError"
    assert "frame exceeds" in str(result.error["message"])
    assert started["value"] is False
    assert pipes == []


def test_run_isolated_start_failure_returns_supervisor_error_and_closes_pipes(
    monkeypatch,
):
    connections: list[FakeConnection] = []

    class FakeConnection:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def send_bytes(self, payload: bytes) -> None:
            return None

    class FakeProcess:
        pid = None
        exitcode = None

        def start(self) -> None:
            raise RuntimeError("start boom")

        def join(self, timeout: float = 0) -> None:
            raise AssertionError("join must not be called on unstarted process")

        def kill(self) -> None:
            raise AssertionError("kill must not be called on unstarted process")

        def is_alive(self) -> bool:
            raise AssertionError("is_alive must not be called on unstarted process")

    class FakeContext:
        def Pipe(self, duplex: bool = False) -> tuple[FakeConnection, FakeConnection]:
            left = FakeConnection()
            right = FakeConnection()
            connections.extend([left, right])
            return left, right

        def Process(self, **_: object) -> FakeProcess:
            return FakeProcess()

    monkeypatch.setattr(hook_supervisor.mp, "get_context", lambda _name: FakeContext())
    result = run_isolated(
        HookWorkerCall(module="fixture", function="worker"),
        timeout_seconds=1.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["type"] == "RuntimeError"
    assert result.error["message"] == "start boom"
    assert len(connections) == 4
    assert all(connection.closed for connection in connections)


def test_run_isolated_context_failure_returns_supervisor_error(monkeypatch):
    monkeypatch.setattr(
        hook_supervisor.mp,
        "get_context",
        lambda _name: (_ for _ in ()).throw(RuntimeError("context boom")),
    )
    result = run_isolated(
        HookWorkerCall(module="fixture", function="worker"),
        timeout_seconds=1.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["type"] == "RuntimeError"
    assert result.error["message"] == "context boom"


def test_run_isolated_second_pipe_failure_closes_first_pipe(monkeypatch):
    connections: list[FakeConnection] = []

    class FakeConnection:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class FakeContext:
        def __init__(self) -> None:
            self.pipe_calls = 0

        def Pipe(self, duplex: bool = False) -> tuple[FakeConnection, FakeConnection]:
            self.pipe_calls += 1
            if self.pipe_calls == 2:
                raise RuntimeError("pipe boom")
            left = FakeConnection()
            right = FakeConnection()
            connections.extend([left, right])
            return left, right

        def Process(self, **_: object):
            raise AssertionError(
                "Process must not be constructed after second pipe failure"
            )

    monkeypatch.setattr(hook_supervisor.mp, "get_context", lambda _name: FakeContext())
    result = run_isolated(
        HookWorkerCall(module="fixture", function="worker"),
        timeout_seconds=1.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["type"] == "RuntimeError"
    assert result.error["message"] == "pipe boom"
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)


def test_run_isolated_process_construction_failure_closes_pipes(monkeypatch):
    connections: list[FakeConnection] = []

    class FakeConnection:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class FakeContext:
        def Pipe(self, duplex: bool = False) -> tuple[FakeConnection, FakeConnection]:
            left = FakeConnection()
            right = FakeConnection()
            connections.extend([left, right])
            return left, right

        def Process(self, **_: object):
            raise RuntimeError("process boom")

    monkeypatch.setattr(hook_supervisor.mp, "get_context", lambda _name: FakeContext())
    result = run_isolated(
        HookWorkerCall(module="fixture", function="worker"),
        timeout_seconds=1.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["type"] == "RuntimeError"
    assert result.error["message"] == "process boom"
    assert len(connections) == 4
    assert all(connection.closed for connection in connections)


@pytest.mark.parametrize(
    ("ready_message", "message_fragment"),
    [
        ({"kind": "ready"}, "missing pid"),
        ({"kind": "ready", "pid": "123"}, "exact JSON int"),
        ({"kind": "ready", "pid": 123.0}, "exact JSON int"),
        ({"kind": "ready", "pid": True}, "exact JSON int"),
        ({"kind": "ready", "pid": 0}, "pid must be positive"),
        ({"kind": "ready", "pid": 456}, "pid mismatch"),
    ],
)
def test_run_isolated_invalid_ready_pid_uses_structured_cleanup(
    monkeypatch,
    ready_message,
    message_fragment,
):
    connections: list[FakeConnection] = []
    receive_calls = {"count": 0}
    kill_calls = {"count": 0}
    join_calls = {"count": 0}
    isolation_created = {"value": False}

    class FakeConnection:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def send_bytes(self, payload: bytes) -> None:
            return None

    class FakeProcess:
        pid = 123
        exitcode = None

        def __init__(self) -> None:
            self.alive = True

        def start(self) -> None:
            return None

        def join(self, timeout: float = 0) -> None:
            join_calls["count"] += 1

        def kill(self) -> None:
            kill_calls["count"] += 1
            self.alive = False
            self.exitcode = -9

        def is_alive(self) -> bool:
            return self.alive

    class FakeContext:
        def Pipe(self, duplex: bool = False) -> tuple[FakeConnection, FakeConnection]:
            left = FakeConnection()
            right = FakeConnection()
            connections.extend([left, right])
            return left, right

        def Process(self, **_: object) -> FakeProcess:
            return FakeProcess()

    def fake_receive_frame_until(*args, **kwargs):
        receive_calls["count"] += 1
        assert kwargs["stage"] == "startup"
        return ready_message

    def fake_create_isolation(_pid: int):
        isolation_created["value"] = True
        raise AssertionError("isolation must not be created for invalid ready pid")

    monkeypatch.setattr(hook_supervisor.mp, "get_context", lambda _name: FakeContext())
    monkeypatch.setattr(
        hook_supervisor,
        "_receive_frame_until",
        fake_receive_frame_until,
    )
    monkeypatch.setattr(hook_supervisor, "_create_isolation", fake_create_isolation)

    result = run_isolated(
        HookWorkerCall(module="fixture", function="worker"),
        timeout_seconds=1.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["type"] == "ProtocolError"
    assert message_fragment in str(result.error["message"])
    assert receive_calls["count"] == 1
    assert kill_calls["count"] == 1
    assert join_calls["count"] >= 1
    assert isolation_created["value"] is False
    assert len(connections) == 4
    assert all(connection.closed for connection in connections)


def test_run_isolated_reports_cleanup_unverified_from_fault_injection(
    monkeypatch, tmp_path
):
    module_name, extra_path = _write_worker_module(tmp_path)

    class FakeIsolation:
        def terminate_and_verify(self, process, *, started: bool, deadline: float):
            return _CleanupStatus(False, "fault injected")

        def verify_quiescent(self, process, *, started: bool, deadline: float):
            return _CleanupStatus(False, "fault injected")

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        hook_supervisor, "_create_isolation", lambda _pid: FakeIsolation()
    )
    result = run_isolated(
        HookWorkerCall(
            module=module_name,
            function="fast_value",
            args=("alpha",),
            extra_sys_paths=(extra_path,),
        ),
        timeout_seconds=2.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["cleanup_unverified"] is True
    assert result.error["cleanup_error"] == "fault injected"


def _run_isolated_with_fake_process_and_isolation(
    monkeypatch,
    *,
    run_event: str,
    isolate_event: str,
) -> tuple[HookWorkerResult, dict[str, object]]:
    state: dict[str, object] = {
        "receive_calls": 0,
        "kill_calls": 0,
        "join_calls": 0,
        "close_calls": 0,
        "alive": True,
    }
    connections: list[FakeConnection] = []

    class FakeConnection:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def send_bytes(self, payload: bytes) -> None:
            return None

    class FakeProcess:
        pid = 123
        exitcode = None

        def start(self) -> None:
            return None

        def join(self, timeout: float = 0) -> None:
            state["join_calls"] = int(state["join_calls"]) + 1
            if run_event == "success":
                self.exitcode = 0
                state["alive"] = False

        def kill(self) -> None:
            state["kill_calls"] = int(state["kill_calls"]) + 1
            self.exitcode = -9
            state["alive"] = False

        def is_alive(self) -> bool:
            return bool(state["alive"])

    class FakeContext:
        def Pipe(self, duplex: bool = False) -> tuple[FakeConnection, FakeConnection]:
            left = FakeConnection()
            right = FakeConnection()
            connections.extend([left, right])
            return left, right

        def Process(self, **_: object) -> FakeProcess:
            return FakeProcess()

    class FakeIsolation:
        def terminate_and_verify(self, process, *, started: bool, deadline: float):
            if isolate_event == "terminate_raises":
                raise RuntimeError("terminate blew up")
            return _CleanupStatus(True)

        def verify_quiescent(self, process, *, started: bool, deadline: float):
            if isolate_event == "verify_raises":
                raise RuntimeError("verify blew up")
            return _CleanupStatus(True)

        def close(self) -> None:
            state["close_calls"] = int(state["close_calls"]) + 1

    def fake_receive_frame_until(*args, **kwargs):
        state["receive_calls"] = int(state["receive_calls"]) + 1
        if int(state["receive_calls"]) == 1:
            return {"kind": "ready", "pid": 123}
        if run_event == "timeout":
            raise hook_supervisor._MessageTimeout("run")
        if run_event == "operational":
            raise hook_supervisor._WorkerExited(
                "run", 9, "worker exited before sending a complete run frame"
            )
        if run_event == "success":
            state["alive"] = False
            return {"kind": "ok", "value": {"echo": "alpha"}}
        raise AssertionError(f"unexpected run_event: {run_event}")

    monkeypatch.setattr(hook_supervisor.mp, "get_context", lambda _name: FakeContext())
    monkeypatch.setattr(
        hook_supervisor,
        "_receive_frame_until",
        fake_receive_frame_until,
    )
    monkeypatch.setattr(
        hook_supervisor, "_create_isolation", lambda _pid: FakeIsolation()
    )

    result = run_isolated(
        HookWorkerCall(module="fixture", function="worker"),
        timeout_seconds=1.0,
    )
    state["connections"] = connections
    return result, state


def test_run_isolated_raised_terminate_and_verify_on_operational_path(monkeypatch):
    result, state = _run_isolated_with_fake_process_and_isolation(
        monkeypatch,
        run_event="operational",
        isolate_event="terminate_raises",
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["type"] == "WorkerExitError"
    assert result.error["cleanup_unverified"] is True
    assert "terminate_and_verify raised RuntimeError: terminate blew up" in str(
        result.error["cleanup_error"]
    )
    assert state["kill_calls"] == 1
    assert int(state["join_calls"]) >= 1
    assert state["close_calls"] == 1
    assert state["alive"] is False
    assert all(connection.closed for connection in state["connections"])


def test_run_isolated_raised_terminate_and_verify_on_timeout_path(monkeypatch):
    result, state = _run_isolated_with_fake_process_and_isolation(
        monkeypatch,
        run_event="timeout",
        isolate_event="terminate_raises",
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["type"] == "TimeoutError"
    assert result.error["cleanup_unverified"] is True
    assert "terminate_and_verify raised RuntimeError: terminate blew up" in str(
        result.error["cleanup_error"]
    )
    assert state["kill_calls"] == 1
    assert int(state["join_calls"]) >= 1
    assert state["close_calls"] == 1
    assert state["alive"] is False
    assert all(connection.closed for connection in state["connections"])


def test_run_isolated_raised_verify_quiescent_on_success_path(monkeypatch):
    result, state = _run_isolated_with_fake_process_and_isolation(
        monkeypatch,
        run_event="success",
        isolate_event="verify_raises",
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["type"] == "CleanupUnverified"
    assert result.error["cleanup_unverified"] is True
    assert "verify_quiescent raised RuntimeError: verify blew up" in str(
        result.error["cleanup_error"]
    )
    assert state["kill_calls"] == 0
    assert int(state["join_calls"]) >= 1
    assert state["close_calls"] == 1
    assert state["alive"] is False
    assert all(connection.closed for connection in state["connections"])


def test_cleanup_and_return_accepts_already_exited_process():
    original = HookWorkerResult(
        outcome="ok", value={"echo": "alpha"}, elapsed_ms=5, pid=1
    )

    class FakeProcess:
        exitcode = 0

        def __init__(self) -> None:
            self.join_calls = 0

        def is_alive(self) -> bool:
            return False

        def kill(self) -> None:
            raise AssertionError("kill should not be reached")

        def join(self, timeout: float = 0) -> None:
            self.join_calls += 1

    process = FakeProcess()

    result = _cleanup_and_return(
        original,
        process=process,
        started=True,
        isolation=None,
        deadline=time.monotonic() + 1.0,
    )

    assert result == original
    assert process.join_calls == 1


def test_cleanup_and_return_waits_for_delayed_kill_terminal_proof():
    class FakeProcess:
        exitcode = None

        def __init__(self) -> None:
            self.alive = True
            self.kill_calls = 0
            self.join_calls = 0

        def is_alive(self) -> bool:
            return self.alive

        def kill(self) -> None:
            self.kill_calls += 1

        def join(self, timeout: float = 0) -> None:
            self.join_calls += 1
            self.alive = False
            self.exitcode = -9

    process = FakeProcess()
    original = HookWorkerResult(
        outcome="ok", value={"echo": "alpha"}, elapsed_ms=5, pid=1
    )

    result = _cleanup_and_return(
        original,
        process=process,
        started=True,
        isolation=None,
        deadline=time.monotonic() + 1.0,
    )

    assert result == original
    assert process.kill_calls == 1
    assert process.join_calls == 1


def test_cleanup_and_return_converts_kill_failure_to_cleanup_unverified():
    class FakeProcess:
        exitcode = None

        def is_alive(self) -> bool:
            return True

        def kill(self) -> None:
            raise PermissionError("denied")

        def join(self, timeout: float = 0) -> None:
            raise AssertionError("join should not be reached")

    result = _cleanup_and_return(
        HookWorkerResult(outcome="ok", value={"echo": "alpha"}, elapsed_ms=5, pid=1),
        process=FakeProcess(),
        started=True,
        isolation=None,
        deadline=time.monotonic() + 1.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["cleanup_unverified"] is True
    assert "kill" in str(result.error["cleanup_error"])
    assert result.error["original_outcome"] == "ok"


def test_cleanup_and_return_converts_join_failure_to_cleanup_unverified():
    class FakeProcess:
        exitcode = None

        def is_alive(self) -> bool:
            return False

        def kill(self) -> None:
            return None

        def join(self, timeout: float = 0) -> None:
            raise OSError("join boom")

    result = _cleanup_and_return(
        HookWorkerResult(
            outcome="supervisor_error",
            error={"type": "WorkerExitError", "message": "boom", "stage": "run"},
            elapsed_ms=5,
            pid=1,
        ),
        process=FakeProcess(),
        started=True,
        isolation=None,
        deadline=time.monotonic() + 1.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["cleanup_unverified"] is True
    assert "join" in str(result.error["cleanup_error"])


def test_run_isolated_rejects_deadline_overflow():
    call = HookWorkerCall(module="fixture", function="worker")

    with pytest.raises(ValueError, match="overflowed the shared deadline"):
        run_isolated(
            call,
            timeout_seconds=sys.float_info.max,
            startup_timeout_seconds=sys.float_info.max,
        )
    with pytest.raises(ValueError, match="overflowed the shared deadline"):
        run_isolated(
            call,
            timeout_seconds=sys.float_info.max,
            startup_timeout_seconds=1.0,
            exit_timeout_seconds=sys.float_info.max,
        )


def test_run_isolated_recursion_during_recv_becomes_protocol_error(monkeypatch):
    connections: list[FakeConnection] = []
    kill_calls = {"count": 0}
    join_calls = {"count": 0}

    class FakeConnection:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def poll(self, timeout: float) -> bool:
            return True

    class FakeProcess:
        pid = 321
        exitcode = None

        def __init__(self) -> None:
            self.alive = True

        def start(self) -> None:
            return None

        def join(self, timeout: float = 0) -> None:
            join_calls["count"] += 1

        def kill(self) -> None:
            kill_calls["count"] += 1
            self.alive = False
            self.exitcode = -9

        def is_alive(self) -> bool:
            return self.alive

    class FakeContext:
        def Pipe(self, duplex: bool = False) -> tuple[FakeConnection, FakeConnection]:
            left = FakeConnection()
            right = FakeConnection()
            connections.extend([left, right])
            return left, right

        def Process(self, **_: object) -> FakeProcess:
            return FakeProcess()

    monkeypatch.setattr(hook_supervisor.mp, "get_context", lambda _name: FakeContext())
    monkeypatch.setattr(
        hook_supervisor,
        "_recv_json_frame",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RecursionError("deep frame")),
    )

    result = run_isolated(
        HookWorkerCall(module="fixture", function="worker"),
        timeout_seconds=1.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["type"] == "ProtocolError"
    assert "RecursionError" in str(result.error["message"])
    assert kill_calls["count"] == 1
    assert join_calls["count"] >= 1
    assert len(connections) == 4
    assert all(connection.closed for connection in connections)


def test_recv_json_frame_rejects_malformed_utf8():
    context = mp.get_context("spawn")
    reader, writer = context.Pipe()
    try:
        writer.send_bytes(b"\xff")
        with pytest.raises(_ProtocolViolation, match="not valid UTF-8"):
            _recv_json_frame(reader, stage="unit")
    finally:
        reader.close()
        writer.close()


def test_recv_json_frame_rejects_oversized_bytes(monkeypatch):
    monkeypatch.setattr(hook_supervisor, "_FRAME_MAX_BYTES", 64)
    context = mp.get_context("spawn")
    reader, writer = context.Pipe()
    try:
        writer.send_bytes(b"x" * 65)
        with pytest.raises(_ProtocolViolation, match="transport error"):
            _recv_json_frame(reader, stage="unit")
    finally:
        reader.close()
        writer.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only unsupported assertion")
def test_run_isolated_posix_timeout_reports_detached_child_as_unsupported(tmp_path):
    module_name, extra_path = _write_worker_module(tmp_path)
    marker = tmp_path / "detached-child.txt"
    delay = 0.2

    result = run_isolated(
        HookWorkerCall(
            module=module_name,
            function="spawn_child_and_exit_abruptly",
            args=(str(marker), delay, True),
            extra_sys_paths=(extra_path,),
        ),
        timeout_seconds=1.0,
        exit_timeout_seconds=1.0,
    )

    assert result.outcome == "supervisor_error"
    assert result.error is not None
    assert result.error["cleanup_unverified"] is True
    assert "cgroup-v2" in str(result.error["cleanup_error"])
    time.sleep(delay * 2)
    assert marker.exists() is True
