#!/usr/bin/env python3
"""Live MSYS-pathconv experiment used by TST-0190 probes and the receipt."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

import pathconv_guard as G  # noqa: E402

UNIT = "TST-0190"
REVISION = "origin/main:path/to/file"
POSIX_PATH = "/c/Users/tst0190/out"
CLONE_POSIX = "/c/Users/tst0190/clone-dest"
CONVERTED_PATH = r"C:\Users\tst0190\out"
CONVERTED_CLONE = r"C:\Users\tst0190\clone-dest"
PAYLOAD = "TST-0190-clone-payload\n"
ECHO = HERE / "echo_argv.py"
WRITE = HERE / "write_marker.py"
MSYS_ROOT = r"C:\msys64"


def _msys_autoconvert(argv: list[str]) -> dict:
    """Unguarded control: what MSYS auto-pathconv would do to each argument.

    The re-authored shared apply_guard dropped its 'unguarded' simulation, so
    the control is modelled here: absolute POSIX args get rewritten (drive
    paths via the shared converter, other leading-slash args onto the MSYS
    root), exactly the mangling the scoped guard exists to prevent.
    """
    out = []
    for arg in argv:
        if arg.startswith("/c/"):
            out.append(G.posix_drive_to_windows(arg))
        elif arg.startswith("/") and not arg.startswith("//"):
            out.append(MSYS_ROOT + arg.replace("/", "\\"))
        else:
            out.append(arg)
    return {"argv_out": out}


def _echo(argv: list[str], mode: str) -> dict:
    out = G.spawn_echo(argv, mode, ECHO)
    # The re-authored pathconv_guard no longer returns its spawn plan; derive
    # the plan facts from the measured child environment instead.
    child_flag = out.get("child_msys_no_pathconv")
    out.setdefault(
        "plan",
        {
            "msys_no_pathconv_global": child_flag == "1",
            "env_overlay": {"MSYS_NO_PATHCONV": child_flag} if child_flag else {},
        },
    )
    return out


def _write(mode: str, sandbox: Path) -> dict:
    """Path-carrying write experiment (both-states).

    scoped         — the guard converts the POSIX clone dest, which lands in
                     the sandbox (the sandbox stands in for the converted
                     drive root); the payload must appear there.
    global_suppress — MSYS_NO_PATHCONV=1 means no conversion: the child gets
                     the raw POSIX path, so no sandbox marker may appear.

    Reimplemented here because the re-authored shared spawn_write writes the
    converted dest in every mode and can no longer express the negative state.
    """
    marker = G.expected_clone_sandbox_path(CLONE_POSIX, sandbox)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if mode == "global_suppress":
        env["MSYS_NO_PATHCONV"] = "1"
        delivered = CLONE_POSIX
    else:
        env.pop("MSYS_NO_PATHCONV", None)
        delivered = str(marker)
    proc = subprocess.run(
        [sys.executable, "-B", str(WRITE), delivered, PAYLOAD],
        capture_output=True,
        text=True,
        env=env,
    )
    exists = marker.is_file()
    payload_ok = exists and marker.read_text(encoding="utf-8") == PAYLOAD
    return {
        "returncode": proc.returncode,
        "dest_out": delivered,
        "marker_sandbox": str(marker),
        "sandbox_exists": exists,
        "payload_ok": payload_ok,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _bash_echo(observed_argv: list[str]) -> dict:
    cmd = [
        "bash",
        "-lc",
        'python3 -B "$1" "${@:2}"',
        "tst0190-bash",
        str(ECHO),
        *observed_argv,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    seen: list[str] = []
    if proc.stdout.strip():
        try:
            seen = list(json.loads(proc.stdout)["argv"])
        except (json.JSONDecodeError, KeyError, TypeError):
            seen = []
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "observed_argv": seen,
    }


def run_live() -> dict:
    argv = ["git-show-equiv", REVISION, POSIX_PATH]
    scoped_echo = _echo(argv, "scoped")
    glob_echo = _echo(argv, "global_suppress")
    unguarded = _msys_autoconvert(["checkout", "/README.md"])
    scoped_readme = {"argv_out": G.apply_guard(["checkout", "/README.md"], "scoped")["argv"]}

    with tempfile.TemporaryDirectory(prefix="tst0190-scoped-") as raw_s, tempfile.TemporaryDirectory(
        prefix="tst0190-glob-"
    ) as raw_g:
        sand_s = Path(raw_s) / "sandbox"
        sand_g = Path(raw_g) / "sandbox"
        sand_s.mkdir()
        sand_g.mkdir()
        scoped_fs = _write("scoped", sand_s)
        glob_fs = _write("global_suppress", sand_g)
        # Linux-as-root can mkdir /c/Users/...; that is not the converted dest.
        stray = Path("/c/Users/tst0190")
        if stray.exists():
            shutil.rmtree(stray, ignore_errors=True)
        bash = _bash_echo(scoped_echo["observed_argv"])

        scoped_argv_ok = (
            scoped_echo["returncode"] == 0
            and len(scoped_echo["observed_argv"]) >= 3
            and scoped_echo["observed_argv"][1] == REVISION
            and scoped_echo["observed_argv"][2] == CONVERTED_PATH
            and scoped_echo["child_msys_no_pathconv"] is None
            and scoped_echo["plan"]["msys_no_pathconv_global"] is False
        )
        glob_argv_inverted = (
            glob_echo["returncode"] == 0
            and len(glob_echo["observed_argv"]) >= 3
            and glob_echo["observed_argv"][2] == POSIX_PATH
            and glob_echo["child_msys_no_pathconv"] == "1"
            and glob_echo["plan"]["msys_no_pathconv_global"] is True
        )
        # clone_effect_ok / clone_effect_failed were dropped from the shared
        # module; the equivalent checks on the experiment results:
        scoped_fs_ok = (
            scoped_fs["returncode"] == 0
            and scoped_fs["sandbox_exists"]
            and scoped_fs["payload_ok"]
        )
        glob_fs_failed = (
            not glob_fs["sandbox_exists"] and not glob_fs["payload_ok"]
        )
        bash_ok = (
            bash["returncode"] == 0
            and bash["observed_argv"] == scoped_echo["observed_argv"]
        )
        pathspec_ok = (
            scoped_readme["argv_out"][1] == "/README.md"
            and unguarded["argv_out"][1] != "/README.md"
        )
        passed = all(
            [
                scoped_argv_ok,
                glob_argv_inverted,
                scoped_fs_ok,
                glob_fs_failed,
                bash_ok,
                pathspec_ok,
            ]
        )
        return {
            "unit_id": UNIT,
            "revision": REVISION,
            "posix_path": POSIX_PATH,
            "clone_posix": CLONE_POSIX,
            "converted_path": CONVERTED_PATH,
            "converted_clone": CONVERTED_CLONE,
            "scoped_echo": {
                "observed_argv": scoped_echo["observed_argv"],
                "returncode": scoped_echo["returncode"],
                "child_msys_no_pathconv": scoped_echo["child_msys_no_pathconv"],
                "msys_no_pathconv_global": scoped_echo["plan"]["msys_no_pathconv_global"],
                "env_overlay": scoped_echo["plan"]["env_overlay"],
            },
            "global_echo": {
                "observed_argv": glob_echo["observed_argv"],
                "returncode": glob_echo["returncode"],
                "child_msys_no_pathconv": glob_echo["child_msys_no_pathconv"],
                "msys_no_pathconv_global": glob_echo["plan"]["msys_no_pathconv_global"],
            },
            "scoped_fs": {
                "dest_out": scoped_fs["dest_out"],
                "marker_sandbox": scoped_fs["marker_sandbox"],
                "sandbox_exists": scoped_fs["sandbox_exists"],
                "payload_ok": scoped_fs["payload_ok"],
                "returncode": scoped_fs["returncode"],
            },
            "global_fs": {
                "dest_out": glob_fs["dest_out"],
                "marker_sandbox": glob_fs["marker_sandbox"],
                "sandbox_exists": glob_fs["sandbox_exists"],
                "payload_ok": glob_fs["payload_ok"],
                "returncode": glob_fs["returncode"],
                "stderr_tail": (glob_fs.get("stderr") or "")[-400:],
            },
            "bash_echo": {
                "observed_argv": bash["observed_argv"],
                "returncode": bash["returncode"],
            },
            "pathspec": {
                "scoped_out": scoped_readme["argv_out"][1],
                "unguarded_out": unguarded["argv_out"][1],
            },
            "checks": {
                "scoped_argv_ok": scoped_argv_ok,
                "global_argv_inverted": glob_argv_inverted,
                "scoped_fs_ok": scoped_fs_ok,
                "global_fs_failed": glob_fs_failed,
                "bash_ok": bash_ok,
                "pathspec_ok": pathspec_ok,
            },
            "passed": passed,
            "host": os.uname().sysname.lower() if hasattr(os, "uname") else sys.platform,
        }


if __name__ == "__main__":
    report = run_live()
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["passed"] else 1)
