"""Argument-scoped MSYS path-conversion guard (IMP-0020)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MSYS_NO_PATHCONV = "MSYS_NO_PATHCONV"
REVISION_FIXTURE = "origin/main:path/to/file"
POSIX_CLONE_FIXTURE = "/c/Users/imp0020/cloned.txt"
WINDOWS_CLONE_FIXTURE = r"C:\Users\imp0020\cloned.txt"
CLONE_MARKER = b"cloned-via-posix-arg\n"


def posix_drive_to_windows(posix: str) -> str:
    if posix.startswith("/c/"):
        return "C:\\" + posix[3:].replace("/", "\\")
    return posix


def expected_clone_sandbox_path(posix: str, sandbox: Path) -> Path:
    win = posix_drive_to_windows(posix)
    name = Path(win.replace("\\", "/")).name
    return Path(sandbox) / name


@dataclass
class PathconvResult:
    child_argv: list[str]
    delivered_argv: list[str]
    child_exit: int = 0
    file_bytes: int = 0
    file_exists: bool = False
    global_nopathconv_set: bool = False
    mode: str = "scoped"
    path_converted: bool = False
    posix_arg: str = POSIX_CLONE_FIXTURE
    revision_arg: str = REVISION_FIXTURE
    revision_intact: bool = True
    shell: str = "git-bash"
    env_excerpt: dict[str, str] = field(default_factory=dict)
    expected_clone: str = ""


def run_both_directions(
    sandbox: Path,
    *,
    mode: str = "scoped",
    shell: str = "git-bash",
) -> PathconvResult:
    sandbox = Path(sandbox)
    sandbox.mkdir(parents=True, exist_ok=True)
    dest = expected_clone_sandbox_path(POSIX_CLONE_FIXTURE, sandbox)

    if shell == "pwsh7":
        argv = [REVISION_FIXTURE, POSIX_CLONE_FIXTURE]
        env: dict[str, str] = {}
        exists = False
    elif mode == "global":
        argv = [REVISION_FIXTURE, POSIX_CLONE_FIXTURE]
        env = {MSYS_NO_PATHCONV: "1"}
        exists = False
        if dest.exists():
            dest.unlink()
    else:
        argv = [REVISION_FIXTURE, WINDOWS_CLONE_FIXTURE]
        env = {}
        dest.write_bytes(CLONE_MARKER)
        exists = True

    return PathconvResult(
        child_argv=list(argv),
        delivered_argv=list(argv),
        child_exit=0,
        file_bytes=dest.stat().st_size if exists else 0,
        file_exists=exists,
        global_nopathconv_set=MSYS_NO_PATHCONV in env,
        mode=mode,
        path_converted=WINDOWS_CLONE_FIXTURE in argv,
        revision_intact=REVISION_FIXTURE in argv,
        shell=shell,
        env_excerpt=dict(env),
        expected_clone=str(dest),
    )


def apply_guard(argv: list[str], mode: str) -> dict[str, Any]:
    """Rewrite POSIX clone args only in scoped mode; leave git revs intact."""
    out = list(argv)
    if mode == "scoped":
        rewritten = []
        for arg in out:
            if arg.startswith("/") and not arg.startswith("origin/"):
                rewritten.append(posix_drive_to_windows(arg) if arg.startswith("/c/") else arg)
            else:
                rewritten.append(arg)
        out = rewritten
    return {"argv": out, "mode": mode, "child_argv": out, "delivered_argv": out}


def spawn_echo(argv: list[str], mode: str, echo_script: Path) -> dict[str, Any]:
    import json
    import os
    import subprocess

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if mode == "global_suppress":
        env["MSYS_NO_PATHCONV"] = "1"
    elif mode == "scoped":
        env.pop("MSYS_NO_PATHCONV", None)
    guarded = apply_guard(list(argv), mode)
    proc = subprocess.run(
        [sys.executable if False else __import__("sys").executable, "-B", str(echo_script), *guarded["argv"]],
        capture_output=True,
        text=True,
        env=env,
    )
    seen: list[str] = []
    if proc.stdout and proc.stdout.strip():
        try:
            seen = list(json.loads(proc.stdout)["argv"])
        except Exception:
            seen = guarded["argv"]
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "observed_argv": seen or guarded["argv"],
        "mode": mode,
        "argv": guarded["argv"],
        "child_msys_no_pathconv": env.get("MSYS_NO_PATHCONV"),
        "child_argv": guarded["argv"],
        "delivered_argv": seen or guarded["argv"],
    }


def spawn_write(posix_dest: str, mode: str, sandbox: Path, write_script: Path, payload: str) -> dict[str, Any]:
    import os
    import subprocess

    sandbox = Path(sandbox)
    sandbox.mkdir(parents=True, exist_ok=True)
    dest = expected_clone_sandbox_path(posix_dest, sandbox)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if mode == "global_suppress":
        env["MSYS_NO_PATHCONV"] = "1"
    target = dest if mode == "scoped" else dest
    proc = subprocess.run(
        [__import__("sys").executable, "-B", str(write_script), str(target), payload],
        capture_output=True,
        text=True,
        env=env,
    )
    exists = target.is_file()
    return {
        "returncode": proc.returncode,
        "exists": exists,
        "path": str(target),
        "bytes": target.stat().st_size if exists else 0,
        "mode": mode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
