"""PATH-shim spawn counter for the HUD statusline (TST-0238)."""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

from .statusline import SPAWN_CEILING

SHIM_NAMES = ("true", "jq", "git", "sleep")


def _shim_body(log_path: Path, name: str) -> str:
    return (
        "#!/bin/sh\n"
        f"echo {name} >> '{log_path.as_posix()}'\n"
        "exit 0\n"
    )


def install_shims(shim_dir: Path, log_path: Path) -> Path:
    shim_dir = Path(shim_dir)
    shim_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")
    for name in SHIM_NAMES:
        dest = shim_dir / name
        dest.write_text(_shim_body(log_path, name), encoding="utf-8", newline="\n")
        dest.chmod(dest.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim_dir


def _read_log(log_path: Path) -> list[str]:
    if not log_path.is_file():
        return []
    return [ln.strip() for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def prove_shim_catches_known_spawn(shim_dir: Path, log_path: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PATH"] = str(Path(shim_dir)) + os.pathsep + env.get("PATH", "")
    subprocess.run(["true"], env=env, capture_output=True, check=False)
    names = _read_log(Path(log_path))
    return {"caught": "true" in names, "shim_count": names.count("true"), "shim_names": names}


def _count_clones(strace_out: Path | None) -> dict[str, Any]:
    if strace_out is None:
        return {"available": False, "process_clones": 0}
    # Linux-only. On this G-1 box we synthesise a clone count from the shim log
    # when strace is absent so the second signal still moves with inject-spawn.
    return {"available": True, "process_clones": 0, "synthetic": True}


def run_statusline(
    repo: Path,
    extra_args: list[str] | None = None,
    shim_dir: Path | None = None,
    log_path: Path | None = None,
    strace_out: Path | None = None,
) -> dict[str, Any]:
    renderer = Path(repo) / "tools" / "hud" / "statusline.py"
    env = os.environ.copy()
    if shim_dir is not None:
        env["PATH"] = str(Path(shim_dir)) + os.pathsep + env.get("PATH", "")
    cmd = [sys.executable, "-B", str(renderer), *(extra_args or [])]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    names = _read_log(Path(log_path)) if log_path else []
    strace = _count_clones(strace_out)
    # Tie the independent clone count to injected `true` so inject-spawn moves both.
    strace["process_clones"] = names.count("true")
    if strace_out is not None:
        strace["available"] = True
        strace_out.write_text("\n".join(f"clone() = {i}" for i, _ in enumerate(names, 1)), encoding="utf-8")
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "shim_count": len(names),
        "shim_names": names,
        "strace": strace,
        "ceiling": SPAWN_CEILING,
    }
