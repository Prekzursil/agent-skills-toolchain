#!/usr/bin/env python3
from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import compat_diagnostics as cd  # noqa: E402


def test_supported_cell() -> None:
    r = cd.build_report(
        inject={
            "shell": "bash",
            "os_name": "linux",
            "client_name": "cursor",
            "client_version": "1",
            "interpreter_versions": {"python3": "3.12", "node": "20", "bash": "5", "pwsh": None},
        }
    )
    assert r["verdict"] == "SUPPORTED"


def test_unsupported_client() -> None:
    r = cd.build_report(
        inject={
            "shell": "bash",
            "os_name": "linux",
            "client_name": "notepad",
            "interpreter_versions": {"python3": "3.12", "node": None, "bash": "5", "pwsh": None},
        }
    )
    assert r["verdict"] == "UNSUPPORTED"
    assert r["remediation"]


def test_unsupported_shell() -> None:
    r = cd.build_report(
        inject={
            "shell": "cmd.exe",
            "os_name": "windows",
            "client_name": "cursor",
            "interpreter_versions": {"python3": "3.12", "node": None, "bash": None, "pwsh": "7"},
        }
    )
    assert r["verdict"] == "UNMODELLED"
    assert r["cell"]["shell"]["name"] == "cmd.exe"


def test_missing_interpreter() -> None:
    r = cd.build_report(
        inject={
            "shell": "bash",
            "os_name": "linux",
            "client_name": "cursor",
            "interpreter_versions": {"python3": None, "node": None, "bash": "5", "pwsh": None},
        }
    )
    assert r["verdict"] == "UNSUPPORTED"


def test_report_names_measured_from_shell() -> None:
    r = cd.build_report(inject={"shell": "pwsh7", "os_name": "linux", "client_name": "cursor",
                                "interpreter_versions": {"python3": "3.12", "node": None, "bash": None, "pwsh": "7"}})
    assert r["measured_from_shell"]["name"] == "pwsh7"


def test_fabricated_unsupported_cell_has_remediation() -> None:
    r = cd.build_report(
        inject={
            "shell": "fish",
            "os_name": "linux",
            "client_name": "cursor",
            "interpreter_versions": {"python3": "3.12", "node": None, "bash": None, "pwsh": None},
        }
    )
    assert r["verdict"] == "UNMODELLED"
    assert str(r["remediation"]).strip()


def test_cmd_shim_disagreement_is_recorded() -> None:
    with tempfile.TemporaryDirectory() as td:
        shim = Path(td) / "mystery-tool.cmd"
        shim.write_text("@echo off\n", encoding="utf-8")
        os.chmod(shim, stat.S_IRUSR | stat.S_IWUSR)
        rec = cd.dual_resolve("mystery-tool", [td])
        assert rec["posix_which"] is None
        assert rec["disagree"]
        assert str(rec["win_get_command"]).endswith("mystery-tool.cmd")


def test_unmodelled_shell_is_named_not_collapsed() -> None:
    r = cd.build_report(
        inject={
            "shell": "cmd.exe",
            "os_name": "windows",
            "client_name": "cursor",
            "interpreter_versions": {"python3": "3.12", "node": "20", "bash": "5", "pwsh": "7"},
        }
    )
    assert r["cell"]["shell"]["name"] == "cmd.exe"
    assert r["verdict"] == "UNMODELLED"


def main() -> int:
    tests = [
        test_supported_cell,
        test_unsupported_client,
        test_unsupported_shell,
        test_missing_interpreter,
        test_report_names_measured_from_shell,
        test_fabricated_unsupported_cell_has_remediation,
        test_cmd_shim_disagreement_is_recorded,
        test_unmodelled_shell_is_named_not_collapsed,
    ]
    for fn in tests:
        fn()
        print(f"{fn.__name__} ... ok")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
