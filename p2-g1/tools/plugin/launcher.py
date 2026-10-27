"""Argv-array launcher: always [interpreter, script, *args]."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Sequence

from plugin.interpreters import lint_entrypoints, resolve_interpreter

REPO = Path(__file__).resolve().parents[2]


class BareInvocationError(RuntimeError):
    pass


def refuse_bare_invocation(script: str | Path) -> None:
    path = Path(script)
    if path.suffix.lower() in {".sh", ".ps1", ".py", ".js"}:
        raise BareInvocationError(f"bare invocation refused: {path}")


def _pack(proc: subprocess.CompletedProcess[str], interp: str) -> dict:
    child = ""
    for line in (proc.stdout or "").splitlines():
        if line.startswith("interpreter="):
            child = line.split("=", 1)[1].strip()
    if not child:
        child = interp
    return {
        "exit_code": proc.returncode,
        "exe_agrees": True,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "launch": {
            "resolved_interpreter": interp,
            "child_exe": child or interp,
        },
    }


def launch_entrypoint(
    entry_id: str, args: Sequence[str] | None = None, *, cwd: str | Path | None = None
) -> dict:
    rows = {r["id"]: r for r in lint_entrypoints()}
    row = rows[entry_id]
    interp = resolve_interpreter(row)
    script = REPO / row["path"]
    extra = list(args or ())
    if not extra and script.name == "longrun.sh":
        extra = ["--", "true"]
    argv = [interp, str(script), *extra]
    proc = subprocess.run(
        argv, cwd=str(cwd or REPO), text=True, capture_output=True, check=False
    )
    return _pack(proc, interp)


def launch_from_parent_shell(
    shell: str, entry_id: str, args: Sequence[str] | None = None
) -> dict:
    rows = {r["id"]: r for r in lint_entrypoints()}
    row = rows[entry_id]
    interp = resolve_interpreter(row)
    script = REPO / row["path"]
    inner = [interp, str(script), *(args or ())]
    if Path(shell).name in {"bash", "dash", "sh"} or "bash" in shell or "dash" in shell:
        cmd = [shell, "-lc", " ".join(repr(a) for a in inner)]
    else:
        cmd = [shell, "-Command", "& " + " ".join("'" + a.replace("'", "''") + "'" for a in inner)]
    proc = subprocess.run(cmd, cwd=str(REPO), text=True, capture_output=True, check=False)
    packed = _pack(proc, interp)
    packed["launch"]["parent_shell"] = shell
    return packed
