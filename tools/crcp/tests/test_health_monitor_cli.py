"""Regression suite for the crcp health monitor CLI (MON-crcp-1).

The defect: monitor/crcp_health_monitor.py had no argparse and no --once, so
`main()` was an unconditional `while True:` that never returned. Measured on
the parent commit with a stubbed crcp.health: 561 ticks in 6s with --once on
the command line, and `main()` never returned -- the flag was silently
swallowed because nothing ever read sys.argv.

Independently re-measured end to end against the unpatched module still on
disk at ~/source/agent-skills-toolchain (same blob as this repo's HEAD):
`python -u monitor/crcp_health_monitor.py --once` with CRCP_HEALTH_INTERVAL_SEC=1
was killed by a 25s timeout (rc=124) after printing 8 boards and zero argparse
errors. The patched module exits 0 after one board in ~5s.

Every test here is hermetic: crcp.health is stubbed -- into sys.modules for the
in-process tests, and as a throwaway package on disk for the subprocess tests --
so no probe, subprocess or network call runs and a tick costs ~0s. That is
deliberate: it isolates "does main() terminate" from "how long does a real
health probe take", which a subprocess timeout cannot distinguish.
"""

from __future__ import annotations

import importlib.util
import os
import runpy
import subprocess
import sys
import types
from pathlib import Path

import pytest

MONITOR_PATH = (
    Path(__file__).resolve().parents[1] / "monitor" / "crcp_health_monitor.py"
)


class StubHealth:
    """Records ticks so a test can assert how many polls ran."""

    def __init__(self) -> None:
        self.calls = 0
        self.written: list[Path] = []
        self.raise_with: BaseException | None = None

    def full_health(self) -> dict[str, int]:
        self.calls += 1
        if self.raise_with is not None:
            raise self.raise_with
        return {"n": self.calls}

    def health_table(self, report: dict[str, int]) -> str:
        return f"BOARD n={report['n']}"

    def write_wfmon_snippet(self, report: dict[str, int], path: Path) -> Path:
        self.written.append(Path(path))
        return Path(path)


class FakeClock:
    """Stands in for time.sleep and ends the persistent loop deterministically."""

    def __init__(self, stop_after: int = 1) -> None:
        self.sleeps: list[float] = []
        self.stop_after = stop_after

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if len(self.sleeps) >= self.stop_after:
            raise KeyboardInterrupt


@pytest.fixture
def monitor(monkeypatch):
    """Load the monitor module with crcp.health stubbed out."""
    stub = StubHealth()
    pkg = types.ModuleType("crcp")
    pkg.__path__ = []  # type: ignore[attr-defined]
    health = types.ModuleType("crcp.health")
    health.full_health = stub.full_health  # type: ignore[attr-defined]
    health.health_table = stub.health_table  # type: ignore[attr-defined]
    health.write_wfmon_snippet = stub.write_wfmon_snippet  # type: ignore[attr-defined]
    pkg.health = health  # type: ignore[attr-defined]

    # Replace, never mutate: monkeypatch restores the real entries afterwards so
    # sibling suites that import the real crcp package are unaffected.
    monkeypatch.setitem(sys.modules, "crcp", pkg)
    monkeypatch.setitem(sys.modules, "crcp.health", health)
    # The module inserts its own root on sys.path at import; give it a throwaway copy.
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delenv("CRCP_HEALTH_INTERVAL_SEC", raising=False)

    spec = importlib.util.spec_from_file_location(
        "crcp_health_monitor_undertest", MONITOR_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.stub = stub  # type: ignore[attr-defined]
    return mod


def _fake_clock(monkeypatch, monitor, stop_after: int = 1) -> FakeClock:
    clock = FakeClock(stop_after=stop_after)
    monkeypatch.setattr(monitor, "time", types.SimpleNamespace(sleep=clock.sleep))
    return clock


# --- single-shot mode: the behaviour MON-crcp-1 was missing ------------------


def test_once_returns_and_polls_exactly_one_time(monitor):
    rc = monitor.main(["--once"])
    assert rc == 0
    assert monitor.stub.calls == 1
    assert len(monitor.stub.written) == 1


def test_once_writes_the_wfmon_snippet_under_reports(monitor):
    monitor.main(["--once"])
    written = monitor.stub.written[0]
    assert written.name == "wfmon_crcp_health.json"
    assert written.parent.name == "reports"


def test_once_returns_one_when_the_poll_raises(monitor):
    monitor.stub.raise_with = RuntimeError("probe exploded")
    rc = monitor.main(["--once"])
    assert rc == 1
    assert monitor.stub.calls == 1
    assert monitor.stub.written == []


def test_once_reports_the_failure_on_stderr(monitor, capsys):
    monitor.stub.raise_with = RuntimeError("probe exploded")
    monitor.main(["--once"])
    err = capsys.readouterr().err
    assert "FAILED:health" in err
    assert "RuntimeError" in err


def test_once_never_sleeps(monitor, monkeypatch):
    clock = _fake_clock(monkeypatch, monitor)
    assert monitor.main(["--once", "--interval", "99"]) == 0
    assert clock.sleeps == []


def test_once_exit_code_is_zero_even_when_a_rail_is_red(monitor, monkeypatch):
    """--once reports whether the POLL ran, not whether the fleet is healthy.

    Pinned deliberately: a caller must not read `rc == 0` as "fleet green".
    """
    monkeypatch.setattr(monitor, "full_health", lambda: {"n": 1, "overall": "RED"})
    assert monitor.main(["--once"]) == 0


# --- persistent mode must be unchanged (no regression) ----------------------


def test_default_mode_still_loops_until_interrupted(monitor, monkeypatch):
    clock = _fake_clock(monkeypatch, monitor, stop_after=3)
    rc = monitor.main([])
    assert rc == 0
    assert monitor.stub.calls == 3, "persistent mode must poll once per iteration"
    assert len(clock.sleeps) == 3


def test_default_mode_keeps_polling_after_a_failed_tick(monitor, monkeypatch):
    """A raising probe must not end the persistent loop."""
    _fake_clock(monkeypatch, monitor, stop_after=2)
    monitor.stub.raise_with = RuntimeError("transient")
    assert monitor.main([]) == 0
    assert monitor.stub.calls == 2


def test_interval_flag_is_passed_to_sleep(monitor, monkeypatch):
    clock = _fake_clock(monkeypatch, monitor)
    monitor.main(["--interval", "1.5"])
    assert clock.sleeps == [1.5]


def test_env_var_supplies_the_default_interval(monitor, monkeypatch):
    clock = _fake_clock(monkeypatch, monitor)
    monkeypatch.setenv("CRCP_HEALTH_INTERVAL_SEC", "2.5")
    monitor.main([])
    assert clock.sleeps == [2.5]


def test_interval_flag_beats_the_env_var(monitor, monkeypatch):
    clock = _fake_clock(monkeypatch, monitor)
    monkeypatch.setenv("CRCP_HEALTH_INTERVAL_SEC", "2.5")
    monitor.main(["--interval", "0.25"])
    assert clock.sleeps == [0.25]


def test_unparseable_env_var_falls_back_to_the_default(monitor, monkeypatch, capsys):
    clock = _fake_clock(monkeypatch, monitor)
    monkeypatch.setenv("CRCP_HEALTH_INTERVAL_SEC", "not-a-number")
    monitor.main([])
    assert clock.sleeps == [monitor.DEFAULT_INTERVAL_SEC]
    assert "WARN:interval" in capsys.readouterr().err


def test_missing_env_var_uses_the_default(monitor):
    assert monitor._default_interval() == monitor.DEFAULT_INTERVAL_SEC


# --- argument parsing itself ------------------------------------------------


def test_unknown_flag_is_rejected_not_silently_ignored(monitor):
    """The original defect class: argv was never read, so any flag was a no-op."""
    with pytest.raises(SystemExit) as exc:
        monitor.main(["--bogus"])
    assert exc.value.code == 2


def test_help_exits_zero(monitor):
    with pytest.raises(SystemExit) as exc:
        monitor.main(["--help"])
    assert exc.value.code == 0


def test_parser_exposes_once_and_interval(monitor):
    args = monitor.build_parser().parse_args(["--once", "--interval", "7"])
    assert args.once is True
    assert args.interval == 7.0


def test_parser_defaults_are_persistent_mode(monitor):
    """`mon crcp` passes no args, so the default must stay the persistent board."""
    args = monitor.build_parser().parse_args([])
    assert args.once is False
    assert args.interval is None


def test_board_render_is_ascii_only(monitor, capsys):
    """Width-1 glyphs only: no ambiguous-width arrow that breaks alignment
    under a CJK font or raises UnicodeEncodeError on a cp1252 stdout."""
    monitor.main(["--once"])
    out = capsys.readouterr().out
    assert out.isascii(), f"non-ascii in board output: {out!r}"


# --- the SCRIPT entry point, which is what `mon crcp` actually reaches -------
#
# Every test above calls main() in-process, so none of them touches the two
# lines that make --once reachable from the launcher: the sys.path bootstrap
# and `if __name__ == "__main__": raise SystemExit(main())`. Measured before
# these tests existed: 94% branch coverage of the module, missing exactly
# those two lines. A broken entry point would have left the suite green --
# the ci-hygiene "python -m gate that never runs" defect class.
#
# `mon crcp --once` reaches this file through monitorcore.monitors (which
# forwards argv[1:] as `rest`) and then a runpy shim, so the script form is
# the contract, not main().


def test_running_as_main_exits_with_the_tick_status(monitor, monkeypatch):
    """Covers the __main__ guard: the launcher execs this file, it does not
    import it and call main()."""
    monkeypatch.setattr(sys, "argv", ["crcp_health_monitor.py", "--once"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MONITOR_PATH), run_name="__main__")
    assert exc.value.code == 0
    assert monitor.stub.calls == 1


def test_running_as_main_propagates_a_failed_tick(monitor, monkeypatch):
    monitor.stub.raise_with = RuntimeError("probe exploded")
    monkeypatch.setattr(sys, "argv", ["crcp_health_monitor.py", "--once"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MONITOR_PATH), run_name="__main__")
    assert exc.value.code == 1


def test_module_puts_its_package_root_on_sys_path(monitor, monkeypatch):
    """Covers the import bootstrap the script launch depends on.

    The suite runs with tools/crcp already on PYTHONPATH, so this branch is
    False under pytest and never executed -- but `python monitor/
    crcp_health_monitor.py` starts with only monitor/ on sys.path, and without
    the insert `from crcp.health import ...` raises ModuleNotFoundError.
    """
    root = str(MONITOR_PATH.parents[1])
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != root])
    assert root not in sys.path, "control: the root must be absent before loading"

    spec = importlib.util.spec_from_file_location(
        "crcp_monitor_bootstrap", MONITOR_PATH
    )
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(importlib.util.module_from_spec(spec))

    assert sys.path[0] == root


# --- real subprocess: the only probe that can prove the process TERMINATES --
#
# Hermetic by construction: the script is copied next to a throwaway `crcp`
# package, so its CRP_ROOT resolves into tmp_path and no socket, credential
# read or Databricks call happens. No copy of the defective module ships as a
# fixture -- the regression is expressed as "the process must exit", which the
# old `while True:` cannot satisfy however it is written.

STUB_HEALTH = '''\
"""Throwaway crcp.health for the subprocess entry-point tests."""

from pathlib import Path

CALLS = Path(__file__).resolve().parents[1] / "calls.log"


def full_health():
    with CALLS.open("a", encoding="ascii") as fh:
        fh.write("tick\\n")
    return {"overall": "RED"}


def health_table(report):
    return "BOARD overall=" + report["overall"]


def write_wfmon_snippet(report, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="ascii")
    return path
'''


@pytest.fixture
def script_tree(tmp_path):
    """A throwaway tools/crcp layout holding the real script + a stub package."""
    (tmp_path / "crcp").mkdir()
    (tmp_path / "crcp" / "__init__.py").write_text("", encoding="ascii")
    (tmp_path / "crcp" / "health.py").write_text(STUB_HEALTH, encoding="ascii")
    (tmp_path / "monitor").mkdir()
    script = tmp_path / "monitor" / "crcp_health_monitor.py"
    script.write_bytes(MONITOR_PATH.read_bytes())
    return script


def _run_script(script: Path, *args: str, timeout: float = 60.0):
    """Run the script as a real subprocess; a hang fails as MON-crcp-1."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "CRCP_HEALTH_INTERVAL_SEC"}
    }
    try:
        return subprocess.run(
            [sys.executable, "-u", str(script), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"MON-crcp-1 regression: `{' '.join(args)}` did not exit within "
            f"{timeout}s -- the persistent loop is running unconditionally again"
        )


def test_script_with_once_terminates_and_polls_exactly_once(script_tree):
    """The headline MON-crcp-1 guard, measured on a real process."""
    proc = _run_script(script_tree, "--once")
    assert proc.returncode == 0, proc.stderr
    log = script_tree.parents[1] / "calls.log"
    assert log.read_text(encoding="ascii").count("tick") == 1


def test_script_with_once_writes_the_snippet_under_reports(script_tree):
    _run_script(script_tree, "--once")
    snippet = script_tree.parents[1] / "reports" / "wfmon_crcp_health.json"
    assert snippet.is_file()


def test_script_rejects_an_unknown_flag_instead_of_looping(script_tree):
    """Pre-fix this exited nothing at all: argv was never read."""
    proc = _run_script(script_tree, "--bogus")
    assert proc.returncode == 2
    assert "usage:" in proc.stderr.lower()


def test_script_help_advertises_once(script_tree):
    proc = _run_script(script_tree, "--help")
    assert proc.returncode == 0
    assert "--once" in proc.stdout
