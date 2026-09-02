"""Detect the OS and shells this box actually has."""
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def is_wsl() -> bool:
    ver = _read_text(Path("/proc/version")).lower()
    rel = _read_text(Path("/proc/sys/kernel/osrelease")).lower()
    if "microsoft" in ver or "wsl" in ver or "microsoft" in rel:
        return True
    return Path("/proc/sys/fs/binfmt_misc/WSLInterop").is_file()


def _which(name: str) -> str | None:
    p = shutil.which(name)
    return p


def _git_bash() -> str | None:
    for cand in (
        "git-bash",
        "/c/Program Files/Git/bin/bash.exe",
        "C:\\Program Files\\Git\\bin\\bash.exe",
        "/usr/bin/bash.exe",
    ):
        p = Path(cand)
        if p.is_file():
            return str(p)
    # MSYS bash advertises msys in `uname -o` when present.
    bash = _which("bash")
    if bash:
        try:
            r = subprocess.run(
                [bash, "-c", "uname -o 2>/dev/null || true"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = (r.stdout or "").strip().lower()
            if "msys" in out or "cygwin" in out:
                return bash
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


def detect() -> dict:
    system = platform.system()
    os_name = {"Linux": "Linux", "Darwin": "macOS", "Windows": "Windows"}.get(
        system, system
    )
    wsl = bool(os_name == "Linux" and is_wsl())
    sh = _which("sh")
    pwsh = _which("pwsh")
    cmd = _which("cmd.exe") or _which("cmd")
    zsh = _which("zsh")
    bash = _which("bash")
    git_bash = _git_bash()
    wsl_bash = None
    if wsl and bash:
        wsl_bash = bash
    macos_zsh = zsh if os_name == "macOS" else None
    shells = {
        "POSIX sh": sh,
        "PowerShell 7": pwsh,
        "cmd.exe": cmd,
        "Git Bash/MSYS": git_bash,
        "WSL bash": wsl_bash,
        "macOS zsh": macos_zsh,
    }
    sh_target = None
    if sh:
        try:
            sh_target = str(Path(sh).resolve())
        except OSError:
            sh_target = sh
    return {
        "os": os_name,
        "system": system,
        "platform": platform.platform(),
        "wsl": wsl,
        "python": platform.python_version(),
        "shells": shells,
        "bash": bash,
        "sh_resolves_to": sh_target,
        "uname": platform.uname()._asdict(),
    }


def cell_available(os_name: str, shell: str, host: dict) -> tuple[bool, str]:
    if host["os"] != os_name:
        return False, f"host os is {host['os']}; cell os is {os_name}"
    path = host["shells"].get(shell)
    if not path:
        extra = ""
        if shell == "WSL bash" and host["os"] == "Linux" and not host["wsl"]:
            extra = " (native Linux, not a WSL instance)"
        if shell == "macOS zsh" and host["os"] != "macOS":
            extra = " (macOS zsh is not a Linux zsh even if zsh were installed)"
        return False, f"shell {shell!r} is not present on this host{extra}"
    return True, path
