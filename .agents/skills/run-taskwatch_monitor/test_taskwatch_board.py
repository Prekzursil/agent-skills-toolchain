#!/usr/bin/env python
"""Tests for the `mon taskwatch` bridge. Run: python test_taskwatch_board.py (or pytest).

The shim's whole job is working out HOW to run taskwatch, so the resolution
ladder is what gets pinned: every rung, in order, plus the two failure shapes
that matter — an explicit pointer that is wrong (named, not silently skipped)
and taskwatch simply not installed (exit 3 with the fixing command, never a
quiet success).

``which``, ``runner`` and ``env`` are all injected, so nothing here launches a
process, touches PATH, or needs taskwatch present.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import taskwatch_board as tb  # noqa: E402


def _no_which(_name: str) -> None:
    return None


def _tool_dir(tmp: Path) -> Path:
    """A directory that looks like a taskwatch checkout (cli/app.py present)."""
    d = tmp / "taskwatch_monitor"
    (d / "cli").mkdir(parents=True)
    (d / "cli" / "app.py").write_text("# cli\n", encoding="utf-8")
    return d


# ───────────────────────────── the ladder, in order ─────────────────────────────


def test_explicit_command_wins_over_everything(tmp_path):
    cmd, cwd, reason = tb.resolve(
        ("status",),
        env={"TASKWATCH_CMD": "/opt/tw", "TASKWATCH_HOME": str(_tool_dir(tmp_path))},
        which=lambda _n: "/usr/bin/taskwatch",
        here=tmp_path,
    )
    assert cmd == ["/opt/tw", "status"]
    assert cwd is None
    assert "TASKWATCH_CMD" in reason


def test_path_lookup_is_preferred_over_a_checkout(tmp_path):
    cmd, cwd, reason = tb.resolve(
        ("status", "--watch"),
        env={"TASKWATCH_HOME": str(_tool_dir(tmp_path))},
        which=lambda _n: "/usr/bin/taskwatch",
        here=tmp_path,
    )
    assert cmd == ["/usr/bin/taskwatch", "status", "--watch"]
    assert cwd is None
    assert "on PATH" in reason


def test_taskwatch_home_runs_the_cli_module_in_place(tmp_path):
    tool = _tool_dir(tmp_path)
    cmd, cwd, reason = tb.resolve(
        ("list",), env={"TASKWATCH_HOME": str(tool)}, which=_no_which, here=tmp_path
    )
    assert cmd == [sys.executable, "-m", "cli.app", "list"]
    assert cwd == tool, "the CLI uses relative imports, so cwd must be the tool dir"
    assert "TASKWATCH_HOME" in reason


def test_a_wrong_taskwatch_home_is_named_not_silently_skipped(tmp_path):
    """An explicit pointer that is wrong is a mistake worth reporting. Falling
    through to a guess that happens to work would hide it."""
    empty = tmp_path / "not-taskwatch"
    empty.mkdir()
    cmd, cwd, reason = tb.resolve(
        env={"TASKWATCH_HOME": str(empty)}, which=_no_which, here=tmp_path
    )
    assert cmd is None
    assert cwd is None
    assert "is not a taskwatch checkout" in reason
    assert str(empty) in reason


def test_finds_a_checkout_beside_the_skill(tmp_path):
    skill = tmp_path / "skills" / "run-taskwatch_monitor"
    skill.mkdir(parents=True)
    tool = tmp_path / "tools" / "taskwatch_monitor"
    (tool / "cli").mkdir(parents=True)
    (tool / "cli" / "app.py").write_text("# cli\n", encoding="utf-8")
    cmd, cwd, reason = tb.resolve(env={}, which=_no_which, here=skill)
    assert cmd == [sys.executable, "-m", "cli.app", "status", "--watch"]
    assert cwd == tool.resolve()
    assert "found at" in reason


def test_not_installed_anywhere(tmp_path):
    cmd, cwd, reason = tb.resolve(env={}, which=_no_which, here=tmp_path)
    assert cmd is None
    assert cwd is None
    assert "not found" in reason


def test_identifies_a_checkout_by_its_cli_not_its_name(tmp_path):
    named = tmp_path / "taskwatch_monitor"
    named.mkdir()
    assert not tb._is_tool_dir(named), "the right name alone is not a checkout"
    (named / "cli").mkdir()
    (named / "cli" / "app.py").write_text("x", encoding="utf-8")
    assert tb._is_tool_dir(named)


# ───────────────────────────── main() behaviour ─────────────────────────────


def test_main_launches_and_returns_the_child_status(tmp_path, capsys):
    calls: list[tuple[list[str], str | None]] = []

    def runner(cmd, cwd=None):
        calls.append((cmd, cwd))
        return 0

    rc = tb.main(
        ["status", "--json"],
        runner=runner,
        env={"TASKWATCH_CMD": "/opt/tw"},
        which=_no_which,
        here=tmp_path,
    )
    assert rc == 0
    assert calls == [(["/opt/tw", "status", "--json"], None)]
    assert "[taskwatch]" in capsys.readouterr().out


def test_main_propagates_a_nonzero_child_status(tmp_path):
    rc = tb.main(
        ["status"],
        runner=lambda _c, cwd=None: 7,
        env={"TASKWATCH_CMD": "/opt/tw"},
        which=_no_which,
        here=tmp_path,
    )
    assert rc == 7, "a failing board must not look like a success"


def test_main_defaults_to_the_live_board(tmp_path):
    seen: list[list[str]] = []
    tb.main(
        [],
        runner=lambda c, cwd=None: seen.append(c) or 0,
        env={"TASKWATCH_CMD": "/opt/tw"},
        which=_no_which,
        here=tmp_path,
    )
    assert seen == [["/opt/tw", *tb.DEFAULT_ARGS]]


def test_main_reports_the_install_command_and_exits_3(tmp_path, capsys):
    launched: list[object] = []
    rc = tb.main(
        ["status"],
        runner=lambda c, cwd=None: launched.append(c) or 0,
        env={},
        which=_no_which,
        here=tmp_path,
    )
    assert rc == tb.EXIT_NOT_INSTALLED == 3
    assert not launched, "nothing may be launched when taskwatch is absent"
    err = capsys.readouterr().err
    assert "install.ps1" in err, "name the one command that fixes it"
    assert "TASKWATCH_HOME" in err


def test_main_passes_cwd_through_for_a_checkout(tmp_path):
    tool = _tool_dir(tmp_path)
    seen: list[tuple[list[str], str | None]] = []
    rc = tb.main(
        ["status"],
        runner=lambda c, cwd=None: seen.append((c, cwd)) or 0,
        env={"TASKWATCH_HOME": str(tool)},
        which=_no_which,
        here=tmp_path,
    )
    assert rc == 0
    assert seen[0][1] == str(tool)


# ───────────────────────────── the boundary it keeps ─────────────────────────────


def test_shim_imports_nothing_from_taskwatch_or_monitorcore():
    """It is a bridge, not a merge: no import of either tool, and stdlib only.

    If this ever fails, the shim has started importing one side into the other
    and the two-tools-one-front-door boundary has quietly become a fusion.
    """
    import ast

    tree = ast.parse((HERE / "taskwatch_board.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module.split(".")[0] if node.module else ".")
    assert found <= {"__future__", "os", "pathlib", "shutil", "subprocess", "sys"}, (
        f"unexpected imports: {sorted(found)}"
    )
    for banned in ("rich", "tomlkit", "mcp", "monitorcore", "cli", "core", "ui"):
        assert banned not in found, f"{banned} must not be imported by the shim"


# Floor, not just "no failures": a discovery break would otherwise report PASS
# on 0/0 and gate nothing. Raise it when tests are added.
MIN_TESTS = 13


def main() -> int:
    tests = [
        (n, o)
        for n, o in sorted(globals().items())
        if n.startswith("test_") and callable(o)
    ]
    if len(tests) < MIN_TESTS:
        print(f"RESULT: FAIL  (collected {len(tests)} tests, floor is {MIN_TESTS})")
        return 1
    # The pytest-fixture tests need pytest; under the plain runner, skip those
    # that ask for fixtures and run the rest, so this stays usable either way.
    import inspect
    import tempfile

    failures: list[str] = []
    for name, fn in tests:
        params = inspect.signature(fn).parameters
        with tempfile.TemporaryDirectory() as td:
            kwargs = {}
            if "tmp_path" in params:
                kwargs["tmp_path"] = Path(td)
            if "capsys" in params:
                print(f"  SKIP {name} (needs pytest capsys)")
                continue
            try:
                fn(**kwargs)
            except Exception as exc:  # noqa: BLE001 - the runner reports everything
                failures.append(name)
                print(f"  BAD  {name}: {exc}")
            else:
                print(f"  OK   {name}")
    print(f"\nRESULT: {'PASS' if not failures else 'FAIL'}  ({len(failures)} failed)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
