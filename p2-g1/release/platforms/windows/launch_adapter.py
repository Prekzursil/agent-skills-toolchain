"""Windows launch adapter: PATHEXT/.cmd resolve + argv spawn (IMP-0013).

Launch path is fenced so a source scan can prove it does not shell out to
Git-Bash. POSIX ``command -v`` is a second instrument, never the launch path.

2026-10-24 shard-5 fixes:
* write_cmd_shim now emits a real Windows batch shim. The previous content
  was a POSIX python script with a shebang; cmd.exe executed it line-by-line
  as batch text ("Unable to initialize device PRN") and the shim never
  launched.
* posix_command_v_live falls back to shutil.which("sh")/("bash") so the
  second instrument is LIVE on Windows dev hosts (Git Bash supplies sh)
  instead of a vacuous None because /bin/sh does not exist as a Windows
  drive path.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

PATHEXT_DEFAULT = ".COM;.EXE;.BAT;.CMD;.VBS;.JS;.WS;.MSC"


class LaunchAdapterError(Exception):
    def __init__(self, code: str, message: str, **ctx: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.ctx = ctx

    def to_user_text(self) -> str:
        action = self.ctx.get("action") or "add the tool directory to PATH and retry"
        return (
            "ERROR:" + self.code + " " + self.message + "\n"
            "PATH=" + (self.ctx.get("path") or os.environ.get("PATH", "")) + "\n"
            "action: " + action
        )


@dataclass
class Resolution:
    used_for_launch: str
    get_command_path: str | None
    posix_command_v: str | None
    disagreement: bool
    disagreement_kind: str | None

    def as_json(self) -> dict:
        return {
            "used_for_launch": self.used_for_launch,
            "get_command_path": self.get_command_path,
            "posix_command_v": self.posix_command_v,
            "disagreement": self.disagreement,
            "disagreement_kind": self.disagreement_kind,
        }
def write_cmd_shim(directory: Path, name: str) -> Path:
    """Emit a REAL Windows batch shim (2026-10-24 fix).

    The previous content was a POSIX python script with a shebang; cmd.exe
    executed it line-by-line as batch text, so the shim never launched.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name + ".cmd")
    body = "\r\n".join([
        "@echo off",
        "echo IMP-0013-SHIM-LAUNCHED",
        "echo %*",
        "",
    ])
    path.write_text(body, encoding="utf-8", newline="")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def _path_dirs(path_dirs: list[str] | None) -> list[Path]:
    if path_dirs:
        return [Path(p) for p in path_dirs]
    raw = os.environ.get("PATH", "")
    return [Path(p) for p in raw.split(os.pathsep) if p]


def _pathext() -> list[str]:
    raw = os.environ.get("PATHEXT") or PATHEXT_DEFAULT
    out: list[str] = []
    for e in raw.split(";"):
        e = e.strip()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        if e in out:
            continue
        out.append(e)
        low = e.lower()
        if low not in out:
            out.append(low)
    return out


def get_command(name: str, path_dirs: list[str] | None = None) -> str | None:
    """PATHEXT-aware resolve: exact name first, then name+each PATHEXT suffix."""
    dirs = _path_dirs(path_dirs)
    exts = [""] + list(_pathext())
    for directory in dirs:
        for ext in exts:
            cand = directory / (name + ext)
            if cand.is_file():
                return str(cand)
    return None
def _shebang_interpreter(path: str) -> str | None:
    """Resolve the interpreter named by a #! line, Windows-natively.

    Accepts /usr/bin/env forms and direct paths; applies the python3 ->
    python alias Windows convention needs.
    """
    try:
        first = Path(path).read_bytes().split(b"\n", 1)[0]
    except OSError:
        return None
    if not first.startswith(b"#!"):
        return None
    parts = first[2:].decode("utf-8", "replace").strip().split()
    if not parts:
        return None
    target = parts[-1].rsplit("/", 1)[-1]
    found = shutil.which(target)
    if found is None and target in ("python3", "python"):
        found = shutil.which("python")
    return found


def posix_command_v_live(name: str, path_dirs: list[str] | None = None) -> str | None:
    """Second instrument: POSIX ``command -v`` via a real POSIX shell.

    2026-10-24: shutil.which fallback keeps the second instrument live on
    Windows dev hosts (Git Bash supplies sh/bash), instead of returning a
    vacuous None because /bin/sh does not exist as a Windows drive path.
    """
    sh = Path("/bin/sh")
    if not sh.is_file():
        for cand in ("/usr/bin/sh", "/bin/bash"):
            if Path(cand).is_file():
                sh = Path(cand)
                break
        else:
            found = shutil.which("sh") or shutil.which("bash")
            if found is None:
                return None
            sh = Path(found)
    env = os.environ.copy()
    if path_dirs:
        joined = os.pathsep.join(path_dirs)
        env["PATH"] = joined
    try:
        proc = subprocess.run(
            [str(sh), "-c", 'command -v "$1"', "sh", name],
            capture_output=True, text=True, env=env, timeout=10,
        )
    except OSError:
        return None
    hit = (proc.stdout or "").strip()
    if proc.returncode != 0 or not hit:
        return None
    return hit.splitlines()[0].strip()
def launch(
    name: str,
    argv: list[str] | None = None,
    path_dirs: list[str] | None = None,
    live_posix: bool = False,
) -> tuple[Resolution, subprocess.CompletedProcess[str]]:
    resolved = get_command(name, path_dirs=path_dirs)
    posix = posix_command_v_live(name, path_dirs=path_dirs) if live_posix else None
    if resolved is None:
        raise LaunchAdapterError(
            "TOOL_NOT_FOUND",
            f"tool {name!r} was not found by Get-Command/PATHEXT",
            path=os.pathsep.join(path_dirs or []),
            action="add the tool directory to PATH or install the shim",
        )
    disagreement = False
    kind = None
    if live_posix and posix is None:
        disagreement = True
        kind = "pathext-shim-only"
    elif posix is not None and Path(posix).resolve() != Path(resolved).resolve():
        disagreement = True
        kind = "path-mismatch"
    cmd = [resolved, *(argv or [])]
    # LAUNCH-PATH-BEGIN
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
        )
    except OSError as exc:
        if os.name != "nt" or _shebang_interpreter(resolved) is None:
            raise
        # 2026-10-24: CreateProcess cannot exec shebang scripts
        # (WinError 193). Resolve the #! interpreter directly (no
        # shell, no bash) and spawn it with the script as argv[1].
        interp = _shebang_interpreter(resolved)
        proc = subprocess.run(
            [interp, resolved, *(argv or [])],
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
        )
    # LAUNCH-PATH-END
    resolution = Resolution(
        used_for_launch=resolved,
        get_command_path=resolved,
        posix_command_v=posix,
        disagreement=disagreement,
        disagreement_kind=kind,
    )
    return resolution, proc
