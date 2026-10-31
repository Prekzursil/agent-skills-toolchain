#!/usr/bin/env python3
"""Tests for tools/launcher/explicit_interpreter.py (IMP-0461).

Runs standalone (python3 -B test_explicit_interpreter.py) or under pytest."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent / "explicit_interpreter.py"

spec = importlib.util.spec_from_file_location("explicit_interpreter", MOD)
E = importlib.util.module_from_spec(spec)
sys.modules["explicit_interpreter"] = E
spec.loader.exec_module(E)


def _fake_shells(tmp: Path) -> dict:
    gitbin = tmp / "git" / "usr" / "bin"
    sys32 = tmp / "System32"
    gitbin.mkdir(parents=True, exist_ok=True)
    sys32.mkdir(parents=True, exist_ok=True)
    (gitbin / "bash.exe").write_bytes(b"stub")
    (sys32 / "bash.exe").write_bytes(b"stub")
    return {"msys": [str(gitbin)], "wsl-system": [str(sys32)]}


def test_bare_invocation_refused():
    try:
        E.argv_for("script.sh")
        raise AssertionError("bare invocation not refused")
    except E.BareInvocationRefused:
        pass


def test_resolution_table_both_shells():
    tmp = Path(tempfile.mkdtemp(prefix="imp0461-test-"))
    shells = _fake_shells(tmp)
    table = E.resolve_name("bash", shells)
    assert table.both_consulted is True
    row_paths = [r["path"] for r in table.rows]
    assert all(row_paths), row_paths
    assert table.shells_disagree is True


def test_family_targets_correct_binary():
    tmp = Path(tempfile.mkdtemp(prefix="imp0461-test-"))
    shells = _fake_shells(tmp)
    table = E.resolve_name("bash", shells)
    msys = table.path_for_shell("msys")
    argv = E.argv_for(
        "script.sh", interpreter="bash", family="msys", shells=shells
    )
    assert Path(argv[0]).resolve() == Path(msys).resolve()


def test_crlf_refusal_typed_under_strict_family():
    tmp = Path(tempfile.mkdtemp(prefix="imp0461-test-"))
    shells = _fake_shells(tmp)
    table = E.resolve_name("bash", shells)
    wsl = table.path_for_shell("wsl-system")
    crlf_dir = Path(tempfile.mkdtemp(prefix="imp0461-test2-"))
    crlf = crlf_dir / "crlf.sh"
    crlf.write_bytes(b"#!/bin/bash\r\necho hi\r\n")
    proc = E.launch(crlf, interpreter=wsl, family="wsl-system")
    assert proc.returncode == 2
    assert "CRLF" in (proc.stderr or "")


def test_first_wins_hides_the_other():
    tmp = Path(tempfile.mkdtemp(prefix="imp0461-test3-"))
    shells = _fake_shells(tmp)
    hidden = E.wrong_bash_if_single_path("bash", shells)
    assert hidden["first_wins_hides_the_other"] is True


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print("FAIL", name, type(exc).__name__, exc)
    print("FAILED:test_explicit_interpreter" if failures else "SUCCESS:test_explicit_interpreter 5/5")
    raise SystemExit(1 if failures else 0)
