"""Tests for ``monitorcore.monitors`` — registry loader, trigger-match, and launch-builder.

The subprocess boundary is a FAKE ``runner`` (records argv, can raise per-call) so every rung of
the wt → console ladder is exercised WITHOUT opening a real window. ``sys.executable`` and the
env / ``$HOME`` are monkeypatched so the interpreter- and path-resolution branches run
deterministically on any platform.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from monitorcore import monitors as m

FIX = Path(__file__).parent / "fixtures" / "monitors.toml"


class FakeRunner:
    def __init__(self, raise_on=None):
        self.calls = []
        self.raise_on = raise_on or {}

    def __call__(self, argv, **kw):
        idx = len(self.calls)
        self.calls.append((argv, kw))
        exc = self.raise_on.get(idx)
        if exc is not None:
            raise exc
        return object()


# ───────────────────────── _py ─────────────────────────
def test_py_uses_sys_executable(monkeypatch):
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    assert m._py() == "/usr/bin/python3"


def test_py_falls_back_to_python(monkeypatch):
    monkeypatch.setattr(sys, "executable", "")
    assert m._py() == "python"


# ───────────────────────── default paths ─────────────────────────
def test_default_skills_root(monkeypatch):
    monkeypatch.setattr(os.path, "expanduser", lambda _p: "/home/u")
    assert m.default_skills_root() == os.path.join("/home/u", ".agents", "skills")


def test_default_monitors_path_env_override(monkeypatch):
    monkeypatch.setenv("MONITORCORE_MONITORS_TOML", "/custom/monitors.toml")
    assert m.default_monitors_path() == "/custom/monitors.toml"


def test_default_monitors_path_default(monkeypatch):
    monkeypatch.delenv("MONITORCORE_MONITORS_TOML", raising=False)
    monkeypatch.setattr(os.path, "expanduser", lambda _p: "/home/u")
    assert m.default_monitors_path() == os.path.join(
        "/home/u", ".agents", "skills", "monitor-launcher", "monitors.toml"
    )


# ───────────────────────── load_monitors ─────────────────────────
def test_load_monitors_parses_tables_and_skips_scalar():
    specs = m.load_monitors(str(FIX))
    # the stray top-level `schema = 1` scalar is skipped (non-table)
    assert set(specs) == {"wfmon", "agentmon", "nolaunch"}
    assert specs["wfmon"] == m.MonitorSpec(
        name="wfmon",
        dir="workflow-monitor",
        entry="workflow_monitor.py",
        trigger_tool="Workflow",
    )
    # missing trigger_tool defaults to ""
    assert specs["nolaunch"].trigger_tool == ""


def test_load_monitors_parses_autolaunch_default_and_explicit():
    specs = m.load_monitors(str(FIX))
    # explicit autolaunch is parsed; a monitor without the key defaults to "open"
    assert specs["agentmon"].autolaunch == "remind"
    assert specs["wfmon"].autolaunch == "open"
    assert specs["nolaunch"].autolaunch == "open"


# ───────────────────────── match_triggers ─────────────────────────
def test_match_triggers_maps_task_and_workflow():
    specs = m.load_monitors(str(FIX))
    assert [s.name for s in m.match_triggers(specs, "Task")] == ["agentmon"]
    assert [s.name for s in m.match_triggers(specs, "Workflow")] == ["wfmon"]


def test_match_triggers_empty_trigger_never_matches():
    specs = m.load_monitors(str(FIX))
    # `nolaunch` has an empty trigger_tool → never matched, even by ""
    assert m.match_triggers(specs, "") == []
    assert m.match_triggers(specs, "Nope") == []


# ───────────────────────── resolve_entry ─────────────────────────
def test_resolve_entry_joins_path():
    spec = m.MonitorSpec("wfmon", "workflow-monitor", "workflow_monitor.py", "Workflow")
    assert m.resolve_entry(spec, "/root") == os.path.join(
        "/root", "workflow-monitor", "workflow_monitor.py"
    )


# ───────────────────────── build_*_argv ─────────────────────────
def test_build_wt_argv_explicit_py_and_args():
    assert m.build_wt_argv("agentmon", "/s/a.py", ["--foo", "1"], py="py") == [
        "wt",
        "-w",
        "agentmon",
        "new-tab",
        "--title",
        "agentmon",
        "py",
        "/s/a.py",
        "--foo",
        "1",
    ]


def test_build_wt_argv_default_py(monkeypatch):
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    argv = m.build_wt_argv("wfmon", "/s/w.py")
    assert argv[6] == "/usr/bin/python3"
    assert argv[-1] == "/s/w.py"


def test_build_console_argv_explicit_py():
    assert m.build_console_argv("wfmon", "/s/w.py", py="py") == [
        "cmd",
        "/c",
        "start",
        "wfmon",
        "py",
        "/s/w.py",
    ]


def test_build_console_argv_default_py(monkeypatch):
    monkeypatch.setattr(sys, "executable", "")
    assert m.build_console_argv("wfmon", "/s/w.py")[4] == "python"


def test_launch_argvs_ladder():
    ladder = m.launch_argvs("wfmon", "/s/w.py", py="py")
    assert ladder[0][0] == "wt"
    assert ladder[1][0] == "cmd"


# ───────────────────────── launch ─────────────────────────
def test_launch_wt_success():
    runner = FakeRunner()
    argv = m.launch("wfmon", "/s/w.py", py="py", runner=runner, close_fds=True)
    assert argv is not None and argv[0] == "wt"
    assert len(runner.calls) == 1
    assert runner.calls[0][1] == {"close_fds": True}


def test_launch_falls_back_to_console(monkeypatch):
    runner = FakeRunner(raise_on={0: RuntimeError("no wt")})
    argv = m.launch("wfmon", "/s/w.py", py="py", runner=runner)
    assert argv is not None and argv[0] == "cmd"
    assert [c[0][0] for c in runner.calls] == ["wt", "cmd"]


def test_launch_all_rungs_fail_returns_none():
    runner = FakeRunner(
        raise_on={0: RuntimeError("no wt"), 1: FileNotFoundError("no cmd")}
    )
    assert m.launch("wfmon", "/s/w.py", py="py", runner=runner) is None
    assert len(runner.calls) == 2


# ───────────────────────── main ─────────────────────────
def test_main_no_args_returns_2(capsys):
    assert (
        m.main([], monitors_path=str(FIX), skills_root="/root", runner=FakeRunner())
        == 2
    )
    assert "usage: mon" in capsys.readouterr().out


def test_main_unknown_monitor_returns_1(capsys):
    rc = m.main(
        ["nope"], monitors_path=str(FIX), skills_root="/root", runner=FakeRunner()
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "unknown monitor: nope" in out
    assert "agentmon" in out  # lists the known ones


def test_main_launch_failure_returns_1(capsys):
    runner = FakeRunner(raise_on={0: RuntimeError(), 1: RuntimeError()})
    rc = m.main(["wfmon"], monitors_path=str(FIX), skills_root="/root", runner=runner)
    assert rc == 1
    assert "failed to launch wfmon" in capsys.readouterr().out


def test_main_success_forwards_args(monkeypatch, capsys):
    monkeypatch.setattr(sys, "executable", "py")
    runner = FakeRunner()
    rc = m.main(
        ["agentmon", "--x"], monitors_path=str(FIX), skills_root="/root", runner=runner
    )
    assert rc == 0
    argv = runner.calls[0][0]
    # entry resolved under skills_root/dir, extra args forwarded
    assert argv[7] == os.path.join("/root", "run-agent-monitor", "agentmon.py")
    assert argv[-1] == "--x"
    assert "launched agentmon" in capsys.readouterr().out


def test_main_reads_sys_argv_when_none(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["mon"])
    # no args → usage, rc 2 (exercises the argv=None branch)
    assert m.main(monitors_path=str(FIX), skills_root="/root", runner=FakeRunner()) == 2
