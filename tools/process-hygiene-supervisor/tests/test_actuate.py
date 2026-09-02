"""Tests for the Windows actuator's safety logic (OS boundaries are injected).

The kill path pins ONE process handle from identity validation through
TerminateProcess (a PID cannot be recycled while a handle to it is open), so the
TOCTOU window that `taskkill`'s own OpenProcess reintroduced is closed. Polite
WM_CLOSE is opt-in: Windows has no cooperative stop for windowless console
processes, and `taskkill /PID` without /F is refused for them.
"""

from __future__ import annotations

import json

import pytest

import hygiene
import hygiene_actuate as act

EXE = "C:/Users/x/cursor-agent/versions/1/node.exe"
IDENT = {"created_unix": 500, "executable": EXE}


def policy(**integration) -> dict:
    base = {
        "powershell": "powershell.exe",
        "reaperPath": "C:/reaper.ps1",
        "reaperStateFile": "C:/state.json",
        "reaperEvidenceRoot": "C:/evidence",
        "wslExe": "wsl.exe",
        "politeStopSeconds": 0,
    }
    base.update(integration)
    return {"integration": base}


class FakeRunner:
    def __init__(self, results: dict[str, act.RunResult] | None = None):
        self.calls: list[list[str]] = []
        self.results = results or {}

    def __call__(self, args: list[str]) -> act.RunResult:
        self.calls.append(args)
        key = args[0].split(".")[0]
        if key == "wsl" and len(args) > 2:
            key = f"wsl:{args[2]}"
        return self.results.get(key, act.RunResult(0, ""))


class FakeHandle:
    """Scripted process handle: identity answers, terminate outcome, wait outcome."""

    def __init__(
        self,
        identities,
        *,
        terminate_ok=True,
        exits_after_polite=False,
        exits_after_terminate=True,
    ):
        self.identities = list(identities)
        self.terminate_ok = terminate_ok
        self.exits_after_polite = exits_after_polite
        self.exits_after_terminate = exits_after_terminate
        self.terminated = False
        self.closed = False
        self.waits: list[float] = []

    def identity(self):
        return self.identities.pop(0) if self.identities else None

    def terminate(self):
        # A failed TerminateProcess leaves the process running.
        self.terminated = self.terminate_ok
        return self.terminate_ok

    priority_ok = True

    def set_memory_priority(self, level):
        if not hasattr(self, "priorities"):
            self.priorities = []
        self.priorities.append(level)
        return self.priority_ok

    def wait(self, seconds):
        self.waits.append(seconds)
        if self.terminated:
            return self.exits_after_terminate
        return self.exits_after_polite

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, handles: dict[int, FakeHandle | None | Exception]):
        self.handles = handles
        self.opened: list[int] = []

    def __call__(self, pid: int):
        self.opened.append(pid)
        result = self.handles.get(pid)
        if isinstance(result, Exception):
            raise result
        return result


def member(pid=100, created=500, exe=EXE):
    return hygiene.parse_snapshot(
        {
            "schema": hygiene.SCHEMA_SNAPSHOT,
            "taken_unix": 1000,
            "host": {
                "physical_bytes": 1,
                "free_bytes": 0,
                "commit_total_bytes": 0,
                "commit_limit_bytes": 0,
            },
            "processes": [
                {
                    "pid": pid,
                    "ppid": 1,
                    "name": "node.exe",
                    "executable": exe,
                    "command_line": "node",
                    "created_unix": created,
                    "cpu_seconds": 1.0,
                    "io_bytes": 1,
                    "working_set_bytes": 1,
                    "private_bytes": 1,
                }
            ],
        }
    ).by_pid[pid]


def actuator(opener, runner=None, **integration):
    return act.WindowsActuator(
        policy(**integration), run_id="r", opener=opener, runner=runner or FakeRunner()
    )


def test_forced_kill_pins_the_handle_and_waits_for_exit():
    handle = FakeHandle([IDENT])
    opener = FakeOpener({100: handle})
    result = actuator(opener).stop_tree([member()], graceful_seconds=0)[0]
    assert result.outcome == "forced"
    assert handle.terminated and handle.closed
    assert handle.waits == [act.EXIT_WAIT_SECONDS]
    assert opener.opened == [100]


def test_vanished_before_open_and_exited_after_open_are_not_kills():
    result = actuator(FakeOpener({100: None})).stop_tree(
        [member()], graceful_seconds=0
    )[0]
    assert result.outcome == "vanished"
    handle = FakeHandle([None])  # OpenProcess succeeded but the process already exited
    result = actuator(FakeOpener({100: handle})).stop_tree(
        [member()], graceful_seconds=0
    )[0]
    assert result.outcome == "vanished"
    assert not handle.terminated and handle.closed


def test_changed_identity_aborts_without_terminating():
    handle = FakeHandle([{"created_unix": 999, "executable": EXE}])
    result = actuator(FakeOpener({100: handle})).stop_tree(
        [member()], graceful_seconds=0
    )[0]
    assert result.outcome == "identity-changed"
    assert not handle.terminated and handle.closed
    handle = FakeHandle([{"created_unix": 500, "executable": "C:/other.exe"}])
    result = actuator(FakeOpener({100: handle})).stop_tree(
        [member()], graceful_seconds=0
    )[0]
    assert result.outcome == "identity-changed"


def test_one_second_creation_time_tolerance_matches_cim_rounding():
    handle = FakeHandle([{"created_unix": 501, "executable": EXE.upper()}])
    result = actuator(FakeOpener({100: handle})).stop_tree(
        [member()], graceful_seconds=0
    )[0]
    assert result.outcome == "forced"


def test_access_denied_is_reported_as_failed_not_vanished():
    opener = FakeOpener({100: PermissionError("access denied")})
    result = actuator(opener).stop_tree([member()], graceful_seconds=0)[0]
    assert result.outcome == "failed"
    assert "access denied" in result.detail


def test_terminate_failure_and_survivor_are_failed():
    handle = FakeHandle([IDENT], terminate_ok=False)
    result = actuator(FakeOpener({100: handle})).stop_tree(
        [member()], graceful_seconds=0
    )[0]
    assert result.outcome == "failed"
    assert "TerminateProcess" in result.detail
    handle = FakeHandle([IDENT], exits_after_terminate=False)
    result = actuator(FakeOpener({100: handle})).stop_tree(
        [member()], graceful_seconds=0
    )[0]
    assert result.outcome == "failed"
    assert "still alive" in result.detail


def test_terminate_failure_on_an_already_exited_process_is_forced():
    class RaceHandle(FakeHandle):
        def wait(self, seconds):
            self.waits.append(seconds)
            return True  # gone by the time we look

    handle = RaceHandle([IDENT], terminate_ok=False)
    result = actuator(FakeOpener({100: handle})).stop_tree(
        [member()], graceful_seconds=0
    )[0]
    assert result.outcome == "forced"


def test_polite_stop_is_opt_in_and_honoured_when_the_process_owns_a_window():
    runner = FakeRunner()
    handle = FakeHandle([IDENT], exits_after_polite=True)
    result = actuator(FakeOpener({100: handle}), runner).stop_tree(
        [member()], graceful_seconds=5
    )[0]
    assert result.outcome == "graceful"
    assert runner.calls == [["taskkill", "/PID", "100"]]
    assert not handle.terminated
    assert handle.waits == [5]


def test_polite_stop_refused_for_a_windowless_process_forces_immediately():
    runner = FakeRunner({"taskkill": act.RunResult(1, "", "ERROR: ...forcefully")})
    handle = FakeHandle([IDENT])
    result = actuator(FakeOpener({100: handle}), runner).stop_tree(
        [member()], graceful_seconds=20
    )[0]
    assert result.outcome == "forced"
    assert "polite stop refused (taskkill rc=1)" in result.detail
    assert handle.waits == [act.EXIT_WAIT_SECONDS]  # no 20 s grace burned


def test_polite_stop_that_is_ignored_falls_through_to_terminate():
    runner = FakeRunner()
    handle = FakeHandle([IDENT], exits_after_polite=False)
    result = actuator(FakeOpener({100: handle}), runner).stop_tree(
        [member()], graceful_seconds=5
    )[0]
    assert result.outcome == "forced"
    assert handle.terminated
    assert handle.waits == [5, act.EXIT_WAIT_SECONDS]


def test_stop_tree_keeps_children_first_order_and_isolates_failures():
    opener = FakeOpener(
        {
            101: FakeHandle([IDENT]),
            100: FakeHandle([IDENT], terminate_ok=False, exits_after_terminate=False),
        }
    )
    results = actuator(opener).stop_tree([member(101), member(100)], graceful_seconds=0)
    assert [(r.pid, r.outcome) for r in results] == [(101, "forced"), (100, "failed")]


def test_wsl_terminate_per_distro_and_shutdown_fallback():
    runner = FakeRunner()
    result = actuator(FakeOpener({}), runner).wsl_shutdown(
        distros=["Ubuntu", "Debian"], action="terminate"
    )
    assert result.outcome == "ok"
    assert runner.calls == [
        ["wsl.exe", "--terminate", "Ubuntu"],
        ["wsl.exe", "--terminate", "Debian"],
    ]
    runner = FakeRunner({"wsl:Debian": act.RunResult(1, "")})
    result = actuator(FakeOpener({}), runner).wsl_shutdown(
        distros=["Ubuntu", "Debian"], action="terminate"
    )
    assert result.outcome == "failed"
    assert "Debian" in result.detail
    runner = FakeRunner()
    result = actuator(FakeOpener({}), runner).wsl_shutdown(
        distros=["Ubuntu"], action="shutdown"
    )
    assert runner.calls == [["wsl.exe", "--shutdown"]]
    assert result.outcome == "ok"
    result = actuator(FakeOpener({}), FakeRunner()).wsl_shutdown(
        distros=[], action="terminate"
    )
    assert result.outcome == "ok"
    assert "nothing to terminate" in result.detail


def test_run_reaper_parses_the_last_json_line_and_appends_apply():
    stdout = "noise\n" + json.dumps({"status": "success", "reaped": 2}) + "\n"
    runner = FakeRunner({"powershell": act.RunResult(0, stdout)})
    result = actuator(FakeOpener({}), runner).run_reaper(apply=True)
    assert result["status"] == "success"
    assert result["reaped"] == 2
    assert result["exit_code"] == 0
    assert "-Apply" in runner.calls[0]


def test_run_reaper_without_apply_omits_the_switch():
    runner = FakeRunner({"powershell": act.RunResult(0, "{}")})
    actuator(FakeOpener({}), runner).run_reaper(apply=False)
    assert "-Apply" not in runner.calls[0]


def test_run_reaper_reports_failure_when_no_json_and_nonzero():
    runner = FakeRunner({"powershell": act.RunResult(1, "boom\nnot-json\n")})
    result = actuator(FakeOpener({}), runner).run_reaper(apply=True)
    assert result["exit_code"] == 1
    assert result["status"] == "error"


def test_run_reaper_ignores_a_malformed_json_line():
    runner = FakeRunner({"powershell": act.RunResult(0, "{bad json\n")})
    result = actuator(FakeOpener({}), runner).run_reaper(apply=True)
    assert result["status"] == "success"
    assert result["exit_code"] == 0


def test_filetime_conversion():
    # 2026-09-02T04:50:00Z as a Windows FILETIME (100 ns ticks since 1601-01-01).
    unix = 1_788_324_600
    filetime = (unix + 11_644_473_600) * 10_000_000
    assert act.filetime_to_unix(filetime) == unix


def test_win32_prototypes_reference_real_wintypes_and_a_wide_handle():
    """The kernel32 path only runs on Windows, so this is the closest Linux CI gets.

    Two things a typo would only reveal on the owner's box: every ``wintypes.X``
    the prototypes name must exist, and HANDLE must be pointer-wide - the reason
    the prototypes exist at all is that ctypes' default C-int marshalling would
    truncate a 64-bit handle to 32 bits.
    """
    import ctypes
    import ctypes.wintypes as wintypes
    import pathlib
    import re

    source = pathlib.Path(act.__file__).read_text(encoding="utf-8")
    names = sorted(set(re.findall(r"wintypes\.([A-Za-z_]+)", source)))
    assert names, "prototype block vanished"
    missing = [name for name in names if not hasattr(wintypes, name)]
    assert missing == [], f"unknown ctypes.wintypes names: {missing}"
    assert ctypes.sizeof(wintypes.HANDLE) == ctypes.sizeof(ctypes.c_void_p)
    # every kernel32 function the handle uses is given a prototype
    used = set(re.findall(r"k(?:32\(\))?\.([A-Z][A-Za-z]+)\(", source))
    declared = set(re.findall(r"k\.([A-Z][A-Za-z]+)\.argtypes", source))
    assert used - {"WinDLL"} <= declared, (
        f"kernel32 calls without argtypes: {used - declared}"
    )


def test_default_opener_is_windows_only():
    with pytest.raises(OSError, match="Windows"):
        act._default_open(1)


def test_memory_priority_is_set_on_a_pinned_identity_checked_handle():
    handle = FakeHandle([IDENT])
    result = actuator(FakeOpener({100: handle})).set_memory_priority(member(), 1)
    assert result.outcome == "demoted" and handle.priorities == [1] and handle.closed
    handle = FakeHandle([IDENT])
    result = actuator(FakeOpener({100: handle})).set_memory_priority(member(), 5)
    assert result.outcome == "restored" and handle.priorities == [5]


def test_memory_priority_refuses_recycled_pids_and_reports_failures():
    changed = FakeHandle([{"created_unix": 999, "executable": EXE}])
    result = actuator(FakeOpener({100: changed})).set_memory_priority(member(), 1)
    assert result.outcome == "identity-changed" and not hasattr(changed, "priorities")
    assert (
        actuator(FakeOpener({100: None})).set_memory_priority(member(), 1).outcome
        == "vanished"
    )
    exited = FakeHandle([None])
    assert (
        actuator(FakeOpener({100: exited})).set_memory_priority(member(), 1).outcome
        == "vanished"
    )
    denied = FakeOpener({100: PermissionError("access denied")})
    assert actuator(denied).set_memory_priority(member(), 1).outcome == "failed"
    failing = FakeHandle([IDENT])
    failing.priority_ok = False
    result = actuator(FakeOpener({100: failing})).set_memory_priority(member(), 1)
    assert result.outcome == "failed" and "SetProcessInformation" in result.detail
