#!/usr/bin/env python3
"""IMP-0019 argv-array tests plus glob-argv-guard extensions."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
GUARD = PLUGIN.parent / "glob-argv-guard"
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(GUARD))

import argv_only as ao  # noqa: E402
import glob_argv_guard as gag  # noqa: E402


def test_hostile_filenames_round_trip() -> None:
    got = ao.echo_argv(gag.HOSTILE_FILENAME)
    assert got == [gag.HOSTILE_FILENAME], got


def test_plugin_production_ast_is_clean() -> None:
    findings = gag.scan_plugin(PLUGIN)
    assert findings == [], findings


def test_negative_control_lint_and_corruption() -> None:
    mutant = GUARD / "fixtures" / "concatenated_spawn.py"
    findings = gag.scan_file(mutant)
    kinds = {f.kind for f in findings}
    assert "shell=True" in kinds
    assert "f-string-into-command" in kinds


def test_negative_control_fixture_is_flagged() -> None:
    findings = gag.scan_file(GUARD / "fixtures" / "concatenated_spawn.py")
    assert findings, "concatenated fixture must be flagged"


def test_scan_flags_shell_true_and_fstring() -> None:
    src = """
import subprocess
subprocess.run(f"echo {x}", shell=True)
"""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "bad.py"
        p.write_text(src, encoding="utf-8")
        kinds = {f.kind for f in gag.scan_file(p)}
        assert "shell=True" in kinds
        assert "f-string-into-command" in kinds


def main() -> int:
    tests = [
        test_hostile_filenames_round_trip,
        test_plugin_production_ast_is_clean,
        test_negative_control_lint_and_corruption,
        test_negative_control_fixture_is_flagged,
        test_scan_flags_shell_true_and_fstring,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"{fn.__name__} ... ok")
        except Exception as exc:
            failed += 1
            print(f"{fn.__name__} ... FAIL {exc}")
    if failed:
        print(f"FAILED {failed}/{len(tests)}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
