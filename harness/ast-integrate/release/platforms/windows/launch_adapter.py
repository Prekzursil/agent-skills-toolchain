"""Windows launch adapter: PATHEXT/.cmd resolve + argv spawn (IMP-0013).

Launch path is fenced so a source scan can prove it does not shell out to
Git-Bash. POSIX ``command -v`` is a SECOND instrument, never the launch path.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
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
            f"ERROR:{self.code} {self.message}\n"
            f"PATH={self.ctx.get('path') or os.environ.get('PATH', '')}\n"
            f"action: {action}"
        )


@dataclass
class Resolution:
    used_for_launch: str
    get_command_path: str | None
    posix_command_v: str | None
    disagreement: bool
    disagreement_kind: str | None

    def as_json(self) -> dict[str, Any]:
        return {
            "used_for_launch": self.used_for_launch,
            "get_command_path": self.get_command_path,
            "posix_command_v": self.posix_command_v,
            "disagreement": self.disagreement,
            "disagreement_kind": self.disagreement_kind,
        }


def write_cmd_shim(directory: Path, name: str) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.cmd"
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('IMP-0013-SHIM-LAUNCHED')\n"
        "print(' '.join(sys.argv[1:]))\n",
        encoding="utf-8",
        newline="\n",
    )
    path.chmod(path.stat().st_mode | 0o111)
    return path


def _path_dirs(path_dirs: list[str] | None) -> list[Path]:
    if path_dirs:
        return [Path(p) for p in path_dirs]
    return [Path(p) for p in os.environ.get("PATH", "").split(os.pathsep) if p]


def _pathext() -> list[str]:
    raw = os.environ.get("PATHEXT") or PATHEXT_DEFAULT
    out: list[str] = []
    for e in raw.split(";"):
        e = e.strip()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        if e not in out:
            out.append(e)
        low = e.lower()
        if low not in out:
            out.append(low)
    return out


def get_command(name: str, path_dirs: list[str] | None = None) -> str | None:
    """PATHEXT-aware resolve: exact name first, then name+each PATHEXT suffix."""
    dirs = _path_dirs(path_dirs)
    exts = [""] + [e if e.startswith(".") else f".{e}" for e in _pathext()]
    # Prefer PATHEXT shims (.cmd) over an extensionless miss.
    for directory in dirs:
        for ext in exts:
            cand = directory / f"{name}{ext}"
            if cand.is_file():
                return str(cand)
    return None


def posix_command_v_live(name: str, path_dirs: list[str] | None = None) -> str | None:
    """Second instrument: POSIX ``command -v`` via /bin/sh, never the adapter walker."""
    sh = Path("/bin/sh")
    if not sh.is_file():
        for cand in ("/usr/bin/sh", "/bin/bash"):
            if Path(cand).is_file():
                sh = Path(cand)
                break
        else:
            return None
    env = os.environ.copy()
    if path_dirs:
        env["PATH"] = os.pathsep.join(path_dirs)
    try:
        proc = subprocess.run(
            [str(sh), "-c", 'command -v "$1"', "sh", name],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
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
    proc = subprocess.run(
        cmd,
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
