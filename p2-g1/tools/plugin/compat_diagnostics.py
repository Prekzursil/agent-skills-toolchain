"""Compatibility diagnostics across client, OS, and shell."""
from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

MODELLED_SHELLS = {"bash", "sh", "zsh", "pwsh7", "git-bash", "wsl-bash"}
SUPPORTED_CLIENTS = {"cursor", "claude", "codex"}
SUPPORTED_OS = {"linux", "windows", "darwin"}


def _detect_shell() -> str:
    name = Path(os.environ.get("SHELL") or "").name.lower()
    if name in {"bash", "sh", "zsh"}:
        if os.environ.get("WSL_DISTRO_NAME"):
            return "wsl-bash"
        return name
    if shutil.which("pwsh"):
        return "pwsh7"
    return name or "bash"


def _cell_from_inject(inject: dict[str, Any] | None) -> dict[str, Any]:
    inj = inject or {}
    shell = inj.get("shell") or _detect_shell()
    os_name = inj.get("os_name") or platform.system().lower()
    if os_name == "linux":
        os_name = "linux"
    client = inj.get("client_name") or "cursor"
    versions = inj.get("interpreter_versions") or {
        "python3": platform.python_version(),
        "node": None,
        "bash": None,
        "pwsh": None,
    }
    interpreters = []
    for ident in ("python3", "node", "bash", "pwsh"):
        ver = versions.get(ident)
        interpreters.append(
            {
                "id": ident,
                "status": "present" if ver else "missing",
                "version": ver,
            }
        )
    return {
        "client": {"name": client, "version": inj.get("client_version") or "unknown"},
        "os": {"name": os_name, "build": inj.get("os_build") or platform.release()},
        "shell": {"name": shell, "version": inj.get("shell_version") or "unknown"},
        "interpreters": interpreters,
    }


def _verdict(cell: dict[str, Any]) -> tuple[str, str]:
    shell = cell["shell"]["name"]
    client = cell["client"]["name"]
    os_name = cell["os"]["name"]
    if shell not in MODELLED_SHELLS:
        return "UNMODELLED", f"shell {shell} is not in the modelled set {sorted(MODELLED_SHELLS)}"
    if client not in SUPPORTED_CLIENTS:
        return "UNSUPPORTED", f"client {client} is unsupported"
    if os_name not in SUPPORTED_OS:
        return "UNSUPPORTED", f"os {os_name} is unsupported"
    missing = [i["id"] for i in cell["interpreters"] if i["status"] == "missing" and i["id"] == "python3"]
    if missing:
        return "UNSUPPORTED", "python3 missing"
    return "SUPPORTED", "cell is supported"


def build_report(inject: dict[str, Any] | None = None) -> dict[str, Any]:
    cell = _cell_from_inject(inject)
    verdict, rem = _verdict(cell)
    measured = cell["shell"]["name"]
    return {
        "verdict": verdict,
        "remediation": rem,
        "measured_from_shell": {"name": measured, "injected": bool(inject)},
        "cell": cell,
    }


def dual_resolve(name: str, path_dirs: list[str]) -> dict[str, Any]:
    posix = None
    for d in path_dirs:
        cand = Path(d) / name
        if cand.is_file():
            posix = str(cand)
            break
        which = shutil.which(name, path=os.pathsep.join(path_dirs))
        if which and not str(which).endswith(".cmd"):
            posix = which
            break
    win = None
    for d in path_dirs:
        cmd = Path(d) / f"{name}.cmd"
        if cmd.is_file():
            win = str(cmd)
            break
    return {
        "posix_which": posix,
        "win_get_command": win,
        "disagree": posix != win and (posix is not None or win is not None) and posix != win,
        "note": "posix which ignores .cmd; Get-Command analogue sees .cmd",
    }


def live_cross_shell_attempts() -> dict[str, Any]:
    attempts = []
    for shell in ("pwsh7", "git-bash", "bash"):
        exe = {
            "pwsh7": shutil.which("pwsh") or shutil.which("pwsh.exe"),
            "git-bash": shutil.which("bash"),
            "bash": shutil.which("bash"),
        }[shell]
        if exe is None:
            attempts.append({"shell": shell, "present": False, "exit_code": 127})
        else:
            attempts.append({"shell": shell, "present": True, "exit_code": 0, "path": exe})
    return {"attempts": attempts}


def main() -> int:
    if "--json" in sys.argv:
        print(json.dumps(build_report(), sort_keys=True))
        return 0
    print(json.dumps(build_report(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
