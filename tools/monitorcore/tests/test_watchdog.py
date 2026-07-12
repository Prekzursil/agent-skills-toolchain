"""Tests for ``monitorcore.watchdog`` — freeze detection with an injected runner.

Every subprocess boundary (the PowerShell toast in ``alert``, the ``taskkill`` in
``maybe_kill``) is driven by a FAKE ``runner`` that records argv and can raise — so NO real
toast pops and NO real ``claude.exe`` is killed. Frozen/fresh states are forced by stamping a
fixture transcript's mtime. ``_watch_forever`` is tested directly by injecting a ``sleep`` seam
that raises to drive its exit paths, and is monkeypatched out of the ``main`` dispatch test so
the ``--once`` vs loop routing is covered without an infinite loop.
"""

from __future__ import annotations

import os
from types import SimpleNamespace


from monitorcore import watchdog as wd


class FakeRunner:
    def __init__(self, exc=None):
        self.calls = []
        self.exc = exc

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(returncode=0)


def _make_agent(dir_path, mtime):
    dir_path.mkdir(parents=True, exist_ok=True)
    p = dir_path / "agent-deadbeef.jsonl"
    p.write_text("{}\n", encoding="utf-8")
    os.utime(p, (mtime, mtime))
    return str(p)


# ───────────────────────── newest_jsonl_mtime ─────────────────────────
def test_newest_jsonl_mtime_empty_dir(tmp_path):
    assert wd.newest_jsonl_mtime(str(tmp_path)) == (None, 0.0)


def test_newest_jsonl_mtime_picks_newest(tmp_path):
    old = tmp_path / "agent-old.jsonl"
    new = tmp_path / "agent-new.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    new.write_text("{}\n", encoding="utf-8")
    os.utime(str(old), (1000, 1000))
    os.utime(str(new), (2000, 2000))
    path, mtime = wd.newest_jsonl_mtime(str(tmp_path))
    assert path == str(new) and mtime == 2000


# ───────────────────────── autodetect_subagents_dir ─────────────────────────
def test_autodetect_none_when_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(wd.os.path, "expanduser", lambda _p: str(tmp_path))
    assert wd.autodetect_subagents_dir() is None


def test_autodetect_picks_most_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(wd.os.path, "expanduser", lambda _p: str(tmp_path))
    base = tmp_path / ".claude" / "projects"
    _make_agent(base / "projA" / "sess1" / "subagents", mtime=1000)
    newer = base / "projB" / "sess2" / "subagents"
    _make_agent(newer, mtime=5000)
    # projC (globbed last, alphabetically) has the OLDEST activity -> exercises the
    # ``m > best_m`` FALSE branch after the max is already set.
    _make_agent(base / "projC" / "sess3" / "subagents", mtime=100)
    assert wd.autodetect_subagents_dir() == str(newer)


# ───────────────────────── alert / maybe_kill ─────────────────────────
def test_alert_prints_banner_and_fires_toast(capsys):
    runner = FakeRunner()
    wd.alert("frozen!", runner=runner)
    out = capsys.readouterr().out
    assert "WATCHDOG FREEZE ALERT" in out and "frozen!" in out
    assert runner.calls and runner.calls[0][0] == wd._TOAST_ARGV


def test_alert_swallows_runner_failure(capsys):
    runner = FakeRunner(exc=FileNotFoundError("no powershell"))
    wd.alert("frozen!", runner=runner)  # must not raise
    assert "WATCHDOG FREEZE ALERT" in capsys.readouterr().out


def test_maybe_kill_success(capsys):
    runner = FakeRunner()
    wd.maybe_kill("agent-x.jsonl", runner=runner)
    assert runner.calls[0][0] == ["taskkill", "/IM", "claude.exe", "/T", "/F"]
    assert "sent taskkill" in capsys.readouterr().out


def test_maybe_kill_failure_is_reported(capsys):
    runner = FakeRunner(exc=RuntimeError("boom"))
    wd.maybe_kill(None, runner=runner)
    assert "kill failed: boom" in capsys.readouterr().out


# ───────────────────────── check_once ─────────────────────────
def test_check_once_no_transcripts(tmp_path):
    assert wd.check_once(str(tmp_path), 100.0) == (False, None, 0.0)


def test_check_once_frozen(tmp_path):
    _make_agent(tmp_path, mtime=1000)  # ancient
    frozen, p, age = wd.check_once(str(tmp_path), stale_s=100.0)
    assert frozen is True and p.endswith("agent-deadbeef.jsonl") and age > 100.0


def test_check_once_fresh(tmp_path):
    import time

    _make_agent(tmp_path, mtime=time.time())
    frozen, _p, age = wd.check_once(str(tmp_path), stale_s=10_000.0)
    assert frozen is False and age < 10_000.0


# ───────────────────────── _watch_step ─────────────────────────
def test_watch_step_fresh_clears_latch(tmp_path):
    import time

    _make_agent(tmp_path, mtime=time.time())  # fresh -> not frozen
    runner = FakeRunner()
    # a previous episode had latched "/old"; recovery must clear it and NOT re-alert
    state = wd._watch_step(
        str(tmp_path), 10_000.0, 25.0, "/old", kill=False, runner=runner
    )
    assert state is None
    assert runner.calls == []


def test_watch_step_frozen_new_alerts_and_latches(tmp_path):
    _make_agent(tmp_path, mtime=1000)  # ancient -> frozen
    frozen, p, _age = wd.check_once(str(tmp_path), 100.0)
    assert frozen
    runner = FakeRunner()
    state = wd._watch_step(str(tmp_path), 100.0, 25.0, None, kill=False, runner=runner)
    assert state == p  # latched onto the frozen transcript
    argvs = [c[0] for c in runner.calls]
    assert wd._TOAST_ARGV in argvs  # alert fired
    assert ["taskkill", "/IM", "claude.exe", "/T", "/F"] not in argvs  # kill=False


def test_watch_step_frozen_same_is_throttled(tmp_path):
    _make_agent(tmp_path, mtime=1000)
    frozen, p, _age = wd.check_once(str(tmp_path), 100.0)
    assert frozen
    runner = FakeRunner()
    # already alerted for this exact transcript -> throttled, state unchanged, no new toast
    state = wd._watch_step(str(tmp_path), 100.0, 25.0, p, kill=False, runner=runner)
    assert state == p
    assert runner.calls == []


def test_watch_step_frozen_with_kill(tmp_path):
    _make_agent(tmp_path, mtime=1000)
    runner = FakeRunner()
    state = wd._watch_step(str(tmp_path), 100.0, 25.0, None, kill=True, runner=runner)
    assert state is not None
    argvs = [c[0] for c in runner.calls]
    assert wd._TOAST_ARGV in argvs
    assert ["taskkill", "/IM", "claude.exe", "/T", "/F"] in argvs


# ───────────────────────── _watch_forever ─────────────────────────
def test_watch_forever_stops_on_keyboardinterrupt(tmp_path, capsys):
    _make_agent(tmp_path, mtime=1000)  # frozen -> alerts once before the interrupt
    runner = FakeRunner()

    def fake_sleep(_secs):
        raise KeyboardInterrupt

    rc = wd._watch_forever(
        str(tmp_path),
        100.0,
        25.0,
        kill=False,
        poll=1.0,
        runner=runner,
        sleep=fake_sleep,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "WATCHDOG FREEZE ALERT" in out  # the loop body ran _watch_step -> alert
    assert "[WATCHDOG] stopped." in out


def test_watch_forever_recovers_from_exception(tmp_path, monkeypatch, capsys):
    runner = FakeRunner()
    checks = {"n": 0}

    def flaky_check_once(_d, _stale):
        checks["n"] += 1
        if checks["n"] == 1:
            raise RuntimeError("transient glob error")
        return (False, None, 0.0)  # 2nd iteration: fresh no-op

    monkeypatch.setattr(wd, "check_once", flaky_check_once)

    sleeps = {"n": 0}

    def counting_sleep(_secs):
        # sleep #1 runs inside the exception handler; sleep #2 ends the clean 2nd
        # iteration and is caught by the KeyboardInterrupt branch to exit.
        sleeps["n"] += 1
        if sleeps["n"] >= 2:
            raise KeyboardInterrupt

    rc = wd._watch_forever(
        str(tmp_path),
        100.0,
        25.0,
        kill=False,
        poll=1.0,
        runner=runner,
        sleep=counting_sleep,
    )
    assert rc == 0
    assert "non-fatal: transient glob error" in capsys.readouterr().out


# ───────────────────────── main ─────────────────────────
def test_main_no_dir_returns_1(monkeypatch, capsys):
    monkeypatch.setattr(wd, "autodetect_subagents_dir", lambda: None)
    assert wd.main([]) == 1
    assert "no subagents dir found" in capsys.readouterr().out


def test_main_bad_dir_returns_1(tmp_path):
    missing = str(tmp_path / "nope")
    assert wd.main(["--dir", missing]) == 1


def test_main_once_frozen_alerts_and_kills(tmp_path):
    _make_agent(tmp_path, mtime=1000)  # ancient -> frozen
    runner = FakeRunner()
    rc = wd.main(["--dir", str(tmp_path), "--once", "--kill"], runner=runner)
    assert rc == 2
    argvs = [c[0] for c in runner.calls]
    assert wd._TOAST_ARGV in argvs  # alert toast
    assert ["taskkill", "/IM", "claude.exe", "/T", "/F"] in argvs  # kill


def test_main_once_frozen_without_kill(tmp_path):
    _make_agent(tmp_path, mtime=1000)
    runner = FakeRunner()
    rc = wd.main(["--dir", str(tmp_path), "--once"], runner=runner)
    assert rc == 2
    # alert fired but no taskkill
    assert all(
        c[0] != ["taskkill", "/IM", "claude.exe", "/T", "/F"] for c in runner.calls
    )


def test_main_once_fresh_returns_0(tmp_path, capsys):
    import time

    _make_agent(tmp_path, mtime=time.time())
    rc = wd.main(["--dir", str(tmp_path), "--once", "--stale-min", "60"])
    assert rc == 0
    assert "ok — newest activity" in capsys.readouterr().out


def test_main_loop_mode_delegates_to_watch_forever(tmp_path, monkeypatch):
    _make_agent(tmp_path, mtime=1000)
    sentinel = object()
    captured = {}

    def fake_forever(d, stale_s, stale_min, *, kill, poll, runner, sleep):
        captured.update(dir=d, stale_min=stale_min, kill=kill, poll=poll)
        return sentinel

    monkeypatch.setattr(wd, "_watch_forever", fake_forever)
    rc = wd.main(["--dir", str(tmp_path), "--stale-min", "10", "--poll", "5", "--kill"])
    assert rc is sentinel
    assert captured == {
        "dir": str(tmp_path),
        "stale_min": 10.0,
        "kill": True,
        "poll": 5.0,
    }
