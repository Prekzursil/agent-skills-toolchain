"""Tests for ``monitorcore.spawn`` — the per-agent terminal ladder with an injected runner.

A FAKE ``runner`` records argv + kwargs and can raise per-call, so every rung of the
wt → PowerShell → bare-Python ladder is exercised WITHOUT opening a real window. ``_NEW_CONSOLE``
is monkeypatched to a sentinel so the ``creationflags`` assertion is deterministic on Linux CI
(where the real constant is 0). ``sleep`` is a no-op so the stagger never blocks.
"""

from __future__ import annotations

import sys


from monitorcore import spawn as sp


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


def _rows(*names):
    return [{"name": n, "jsonl": f"/x/agent-{n}.jsonl"} for n in names]


# ───────────────────────── _py ─────────────────────────
def test_py_uses_sys_executable(monkeypatch):
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    assert sp._py() == "/usr/bin/python3"


def test_py_falls_back_to_python(monkeypatch):
    monkeypatch.setattr(sys, "executable", "")
    assert sp._py() == "python"


# ───────────────────────── build_*_argv ─────────────────────────
def test_build_wt_argv_new_window():
    argv = sp.build_wt_argv("/a/agent-x.jsonl", "x", tabs=False, py="py")
    assert argv == [
        "wt",
        "-w",
        "new",
        "--title",
        "x",
        "py",
        "-m",
        "monitorcore.agent_tail",
        "/a/agent-x.jsonl",
    ]


def test_build_wt_argv_tabs():
    argv = sp.build_wt_argv("/a/agent-x.jsonl", "x", tabs=True, py="py")
    assert argv[:6] == ["wt", "-w", "agentmon", "new-tab", "--title", "x"]
    assert argv[-3:] == ["-m", "monitorcore.agent_tail", "/a/agent-x.jsonl"]


def test_build_ps_argv_quotes_and_embeds_module():
    argv = sp.build_ps_argv("/a/agent-x.jsonl", "it's", py="p'y")
    assert argv[:4] == ["powershell", "-NoExit", "-NoProfile", "-Command"]
    inner = argv[4]
    assert "it''s" in inner  # single-quote doubled
    assert "& 'p''y' -m monitorcore.agent_tail '/a/agent-x.jsonl'" in inner


def test_build_py_argv():
    assert sp.build_py_argv("/a/agent-x.jsonl", py="py") == [
        "py",
        "-m",
        "monitorcore.agent_tail",
        "/a/agent-x.jsonl",
    ]


# ───────────────────────── spawn ─────────────────────────
def test_spawn_empty_rows():
    runner = FakeRunner()
    assert (
        sp.spawn([], use_wt=True, tabs=False, runner=runner, sleep=lambda _s: None) == 0
    )
    assert runner.calls == []


def test_spawn_wt_success(monkeypatch):
    monkeypatch.setattr(sp, "_NEW_CONSOLE", 0x10)
    runner = FakeRunner()
    n = sp.spawn(
        _rows("a"), use_wt=True, tabs=True, runner=runner, sleep=lambda _s: None
    )
    assert n == 1
    assert len(runner.calls) == 1
    argv, kw = runner.calls[0]
    assert argv[0] == "wt" and kw == {"close_fds": True}


def test_spawn_wt_failure_falls_back_to_powershell(monkeypatch, capsys):
    monkeypatch.setattr(sp, "_NEW_CONSOLE", 0x10)
    runner = FakeRunner(raise_on={0: RuntimeError("no wt")})
    n = sp.spawn(
        _rows("a"), use_wt=True, tabs=False, runner=runner, sleep=lambda _s: None
    )
    assert n == 1
    assert runner.calls[0][0][0] == "wt"  # attempted wt
    ps_argv, ps_kw = runner.calls[1]
    assert ps_argv[0] == "powershell"
    assert ps_kw == {"creationflags": 0x10, "close_fds": True}
    assert "wt spawn failed" in capsys.readouterr().out


def test_spawn_no_wt_uses_powershell(monkeypatch):
    monkeypatch.setattr(sp, "_NEW_CONSOLE", 0x10)
    runner = FakeRunner()
    sp.spawn(_rows("a"), use_wt=False, tabs=False, runner=runner, sleep=lambda _s: None)
    assert runner.calls[0][0][0] == "powershell"


def test_spawn_powershell_missing_falls_back_to_python(monkeypatch):
    monkeypatch.setattr(sp, "_NEW_CONSOLE", 0)
    runner = FakeRunner(raise_on={0: FileNotFoundError("no powershell")})
    sp.spawn(_rows("a"), use_wt=False, tabs=False, runner=runner, sleep=lambda _s: None)
    # call 0 = powershell (raised), call 1 = bare python fallback
    assert runner.calls[1][0][:3] == [sp._py(), "-m", "monitorcore.agent_tail"]


def test_spawn_wt_failure_persists_across_rows(monkeypatch):
    # after wt fails once, use_wt stays False for the remaining rows (PowerShell only)
    monkeypatch.setattr(sp, "_NEW_CONSOLE", 0)
    runner = FakeRunner(raise_on={0: RuntimeError("no wt")})
    n = sp.spawn(
        _rows("a", "b"), use_wt=True, tabs=False, runner=runner, sleep=lambda _s: None
    )
    assert n == 2
    # a: wt(fail)->ps ; b: ps directly  => calls: wt, ps, ps
    kinds = [c[0][0] for c in runner.calls]
    assert kinds == ["wt", "powershell", "powershell"]
