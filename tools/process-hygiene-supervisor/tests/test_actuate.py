"""Tests for the Windows actuator's safety logic (OS boundaries are injected)."""

from __future__ import annotations

import json

import hygiene
import hygiene_actuate as act


def policy() -> dict:
    return {
        "integration": {
            "powershell": "powershell.exe",
            "reaperPath": "C:/reaper.ps1",
            "reaperStateFile": "C:/state.json",
            "reaperEvidenceRoot": "C:/evidence",
            "wslExe": "wsl.exe",
        }
    }


class FakeRunner:
    def __init__(self, results: dict[str, act.RunResult] | None = None):
        self.calls: list[list[str]] = []
        self.results = results or {}

    def __call__(self, args: list[str]) -> act.RunResult:
        self.calls.append(args)
        key = args[0].split(".")[0]
        if "taskkill" in args[0]:
            key = "taskkill-force" if "/F" in args else "taskkill-graceful"
        return self.results.get(key, act.RunResult(0, ""))


class FakeProber:
    """A scripted process table: each pid maps to a list of per-probe answers."""

    def __init__(self, timeline: dict[int, list[dict | None]]):
        self.timeline = {pid: list(states) for pid, states in timeline.items()}
        self.default = {pid: states[-1] for pid, states in timeline.items()}

    def __call__(self, pid: int):
        states = self.timeline.get(pid)
        if not states:
            return self.default.get(pid)
        return states.pop(0)


class Clock:
    def __init__(self, step: float = 1.0):
        self.t = 0.0
        self.step = step

    def __call__(self) -> float:
        now = self.t
        self.t += self.step
        return now


def member(pid=100, created=500, exe="C:/Users/x/cursor-agent/versions/1/node.exe"):
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


def actuator(runner, prober, **kw):
    return act.WindowsActuator(
        policy(),
        run_id="r",
        runner=runner,
        prober=prober,
        clock=Clock(),
        sleeper=lambda _s: None,
        poll_seconds=1.0,
        **kw,
    )


IDENT = {
    "created_unix": 500,
    "executable": "C:/Users/x/cursor-agent/versions/1/node.exe",
}


def test_graceful_stop_exits_without_force():
    runner = FakeRunner()
    prober = FakeProber({100: [IDENT, IDENT, None]})  # revalidate, alive, then gone
    result = actuator(runner, prober).stop_tree([member()], graceful_seconds=5)[0]
    assert result.outcome == "graceful"
    assert ["taskkill", "/PID", "100"] in runner.calls
    assert not any("/F" in call for call in runner.calls)


def test_force_kill_after_graceful_window():
    runner = FakeRunner()
    # revalidate, two "still alive" polls across the 3s window, then gone after /F.
    prober = FakeProber({100: [IDENT, IDENT, IDENT, None]})
    result = actuator(runner, prober).stop_tree([member()], graceful_seconds=3)[0]
    assert result.outcome == "forced"
    assert ["taskkill", "/PID", "100", "/F"] in runner.calls


def test_force_kill_when_graceful_disabled():
    runner = FakeRunner()
    prober = FakeProber({100: [IDENT, None]})
    result = actuator(runner, prober).stop_tree([member()], graceful_seconds=0)[0]
    assert result.outcome == "forced"
    assert runner.calls == [["taskkill", "/PID", "100", "/F"]]


def test_survivor_is_reported_as_failed():
    runner = FakeRunner()
    prober = FakeProber({100: [IDENT, IDENT]})  # revalidate ok, still alive after /F
    result = actuator(runner, prober).stop_tree([member()], graceful_seconds=0)[0]
    assert result.outcome == "failed"


def test_pid_that_vanished_before_the_kill_is_not_touched():
    runner = FakeRunner()
    prober = FakeProber({100: [None]})
    result = actuator(runner, prober).stop_tree([member()], graceful_seconds=5)[0]
    assert result.outcome == "vanished"
    assert runner.calls == []


def test_changed_identity_aborts_the_kill():
    runner = FakeRunner()
    prober = FakeProber(
        {100: [{"created_unix": 999, "executable": IDENT["executable"]}]}
    )
    result = actuator(runner, prober).stop_tree([member()], graceful_seconds=0)[0]
    assert result.outcome == "identity-changed"
    assert runner.calls == []


def test_recycled_pid_after_force_counts_as_gone():
    runner = FakeRunner()
    prober = FakeProber(
        {100: [IDENT, {"created_unix": 4242, "executable": "C:/other.exe"}]}
    )
    result = actuator(runner, prober).stop_tree([member()], graceful_seconds=0)[0]
    assert result.outcome == "forced"


def test_stop_tree_processes_children_first_order_verbatim():
    runner = FakeRunner()
    prober = FakeProber({100: [IDENT, None], 101: [IDENT, None]})
    tree = [member(101, exe="C:/Users/x/cursor-agent/versions/1/node.exe"), member(100)]
    results = actuator(runner, prober).stop_tree(tree, graceful_seconds=0)
    assert [r.pid for r in results] == [101, 100]


def test_wsl_shutdown_reports_outcome():
    ok = actuator(FakeRunner(), FakeProber({})).wsl_shutdown()
    assert ok.outcome == "ok"
    fail = actuator(
        FakeRunner({"wsl": act.RunResult(1, "")}), FakeProber({})
    ).wsl_shutdown()
    assert fail.outcome == "failed"


def test_run_reaper_parses_the_last_json_line_and_appends_apply():
    stdout = "noise\n" + json.dumps({"status": "success", "reaped": 2}) + "\n"
    runner = FakeRunner({"powershell": act.RunResult(0, stdout)})
    result = actuator(runner, FakeProber({})).run_reaper(apply=True)
    assert result["status"] == "success"
    assert result["reaped"] == 2
    assert result["exit_code"] == 0
    assert "-Apply" in runner.calls[0]


def test_run_reaper_without_apply_omits_the_switch():
    runner = FakeRunner({"powershell": act.RunResult(0, "{}")})
    actuator(runner, FakeProber({})).run_reaper(apply=False)
    assert "-Apply" not in runner.calls[0]


def test_run_reaper_reports_failure_when_no_json_and_nonzero():
    runner = FakeRunner({"powershell": act.RunResult(1, "boom\nnot-json\n")})
    result = actuator(runner, FakeProber({})).run_reaper(apply=True)
    assert result["exit_code"] == 1
    assert result["status"] == "error"


def test_run_reaper_ignores_a_malformed_json_line():
    runner = FakeRunner({"powershell": act.RunResult(0, "{bad json\n")})
    result = actuator(runner, FakeProber({})).run_reaper(apply=True)
    assert result["status"] == "success"
    assert result["exit_code"] == 0
