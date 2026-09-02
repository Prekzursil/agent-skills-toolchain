"""Two-shell Gemini-rail detector.

Availability is settled by (1) a Get-Command analogue that sees PATHEXT/.cmd
shims and a live pwsh Get-Command when PowerShell exists, AND (2) an actual
invocation. Git Bash `which` / POSIX `command -v` are recorded, never used as
the settling absence proof (they miss .cmd shims).

Environment values are never returned or printed — only name, present, bytes.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

WIN_PATHEXT = (".COM", ".EXE", ".BAT", ".CMD")
ABSENT_BIN = "res0024-absent-bin-9f3c2e"
TARGET = "gemini"
AUTH_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY")
PWSH_NAMES = ("pwsh", "pwsh.exe", "powershell", "powershell.exe")
GIT_BASH_NAMES = (
    "git-bash",
    "git-bash.exe",
    "bash.exe",
)
GIT_BASH_PATHS = (
    "/mnt/c/Program Files/Git/bin/bash.exe",
    "/mnt/c/Program Files/Git/usr/bin/bash.exe",
    "C:/Program Files/Git/bin/bash.exe",
    "C:/Program Files/Git/usr/bin/bash.exe",
)


def path_dirs(path_value: str | None = None) -> list[str]:
    raw = path_value if path_value is not None else os.environ.get("PATH", "")
    return [p for p in raw.split(os.pathsep) if p]


def posix_which(name: str, dirs: list[str] | None = None) -> str | None:
    """POSIX which: exact name, executable bit required. Not a settling signal."""
    for directory in dirs if dirs is not None else path_dirs():
        candidate = Path(directory) / name
        try:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        except OSError:
            continue
    return None


def win_get_command(
    name: str,
    dirs: list[str] | None = None,
    pathext: tuple[str, ...] = WIN_PATHEXT,
) -> str | None:
    """Get-Command analogue: PATHEXT, existence (not +x) is enough."""
    exts: list[str] = []
    for ext in pathext:
        if ext not in exts:
            exts.append(ext)
        low = ext.lower()
        if low not in exts:
            exts.append(low)
    has_ext = bool(Path(name).suffix)
    names = [name] if has_ext else [name] + [name + ext for ext in exts]
    for directory in dirs if dirs is not None else path_dirs():
        for n in names:
            candidate = Path(directory) / n
            try:
                if candidate.is_file():
                    return str(candidate)
            except OSError:
                continue
    return None


def dual_resolve(name: str, dirs: list[str] | None = None) -> dict[str, Any]:
    posix = posix_which(name, dirs)
    win = win_get_command(name, dirs)
    disagree = (posix or "") != (win or "")
    rec: dict[str, Any] = {
        "tool": name,
        "posix_which": posix,
        "win_get_command": win,
        "disagree": bool(disagree),
        "posix_which_is_settling_signal": False,
        "win_get_command_is_settling_signal": True,
    }
    if disagree:
        rec["note"] = (
            "POSIX which and Get-Command/PATHEXT disagree. A .cmd/.bat shim "
            "is the usual cause; both readings are kept."
        )
    return rec


def invoke(argv: list[str], timeout: float = 12.0) -> dict[str, Any]:
    """Actual invocation. FileNotFound is a reading, not an exception leak."""
    rec: dict[str, Any] = {
        "argv": list(argv),
        "ran": False,
        "exit_code": 127,
        "stdout_head": "",
        "stderr_head": "",
        "error": None,
        "is_settling_signal": True,
    }
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        rec["error"] = "file-not-found"
        return rec
    except subprocess.TimeoutExpired:
        rec["error"] = "timeout"
        rec["exit_code"] = 124
        rec["ran"] = True
        return rec
    rec["ran"] = True
    rec["exit_code"] = int(proc.returncode)
    rec["stdout_head"] = (proc.stdout or "")[:400]
    rec["stderr_head"] = (proc.stderr or "")[:400]
    return rec


def find_binary(names: tuple[str, ...], extra_paths: tuple[str, ...] = ()) -> str | None:
    for n in names:
        hit = shutil.which(n)
        if hit:
            return hit
    for p in extra_paths:
        if Path(p).is_file():
            return p
    return None


def pwsh_get_command(name: str) -> dict[str, Any]:
    exe = find_binary(PWSH_NAMES)
    rec: dict[str, Any] = {
        "shell": "powershell-7",
        "shell_present": bool(exe),
        "shell_path": exe,
        "tool": name,
        "resolved": None,
        "exit_code": None,
        "error": None,
        "is_settling_signal": True,
        "instrument": "live-pwsh-Get-Command",
    }
    if not exe:
        rec["error"] = "pwsh-not-found"
        rec["instrument"] = "live-pwsh-Get-Command-absent"
        return rec
    script = (
        f"$c = Get-Command -Name {name} -ErrorAction SilentlyContinue; "
        "if ($null -eq $c) { exit 3 }; "
        "Write-Output $c.Source; exit 0"
    )
    try:
        proc = subprocess.run(
            [exe, "-NoProfile", "-NoLogo", "-Command", script],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except FileNotFoundError:
        rec["error"] = "pwsh-not-found"
        rec["shell_present"] = False
        return rec
    rec["exit_code"] = int(proc.returncode)
    out = (proc.stdout or "").strip()
    if proc.returncode == 0 and out:
        rec["resolved"] = out.splitlines()[0].strip()
    elif proc.returncode == 3:
        rec["resolved"] = None
    else:
        rec["error"] = (proc.stderr or proc.stdout or "pwsh-nonzero")[:200]
    return rec


def git_bash_probe(name: str) -> dict[str, Any]:
    """Report Git Bash presence. Do not settle availability on its which."""
    exe = find_binary(GIT_BASH_NAMES, GIT_BASH_PATHS)
    rec: dict[str, Any] = {
        "shell": "git-bash",
        "shell_present": bool(exe),
        "shell_path": exe,
        "tool": name,
        "which_resolved": None,
        "error": None,
        "is_settling_signal": False,
        "note": (
            "Git Bash which is recorded only. A miss here is not evidence of "
            "absence because .cmd shims are invisible to it."
        ),
    }
    if not exe:
        rec["error"] = "git-bash-not-found"
        return rec
    try:
        proc = subprocess.run(
            [exe, "-lc", f"command -v {name} || true"],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except FileNotFoundError:
        rec["error"] = "git-bash-not-found"
        rec["shell_present"] = False
        return rec
    rec["which_resolved"] = (proc.stdout or "").strip() or None
    rec["exit_code"] = int(proc.returncode)
    return rec


def version_from_invocation(inv: dict[str, Any]) -> str | None:
    if not inv.get("ran") or inv.get("exit_code") != 0:
        return None
    text = (inv.get("stdout_head") or "") + "\n" + (inv.get("stderr_head") or "")
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return None


def env_presence(names: tuple[str, ...] = AUTH_VARS) -> list[dict[str, Any]]:
    rows = []
    for name in names:
        raw = os.environ.get(name)
        rows.append(
            {
                "name": name,
                "present": bool(raw),
                "bytes": len(raw.encode("utf-8")) if raw else 0,
            }
        )
    return rows


def gemini_home_surface(home: Path | None = None) -> dict[str, Any]:
    root = (home or Path.home()) / ".gemini"
    def exists(rel: str) -> bool:
        return (root / rel).exists()

    return {
        "path": str(root),
        "present": root.is_dir(),
        "gemini_md": exists("GEMINI.md"),
        "extensions_dir": exists("extensions"),
        "settings_json": exists("settings.json"),
        "google_accounts": exists("google_accounts.json"),
        "oauth_creds_present": any(
            (root / n).is_file()
            for n in ("oauth_creds.json", "credentials.json", "access-tokens.json")
        ),
    }


def two_shell_availability(target: str = TARGET) -> dict[str, Any]:
    analogue = dual_resolve(target)
    invocation = invoke([target, "--version"])
    pwsh = pwsh_get_command(target)
    gitbash = git_bash_probe(target)
    posix_cmd = posix_which(target)
    version = version_from_invocation(invocation)
    get_command_hit = bool(pwsh.get("resolved") or analogue.get("win_get_command"))
    invocation_ok = bool(invocation.get("ran") and invocation.get("exit_code") == 0)
    settled = bool(get_command_hit and invocation_ok)
    fallback = not settled
    return {
        "target": target,
        "settled_available": settled,
        "fallback_required": fallback,
        "program_may_assign_gemini_units": settled,
        "version_from_invocation": version,
        "settling_rule": (
            "availability is settled by Get-Command in PowerShell AND an "
            "invocation, never by which in Git Bash, which misses .cmd shims"
        ),
        "powershell_get_command": pwsh,
        "get_command_analogue": analogue,
        "invocation": invocation,
        "git_bash": gitbash,
        "posix_command_v_non_settling": posix_cmd,
        "posix_bash_present": bool(shutil.which("bash") or Path("/bin/bash").is_file()),
        "two_shell_availability_verdict": (
            "UNAVAILABLE"
            if fallback
            else "AVAILABLE"
        ),
    }


def negative_control(name: str = ABSENT_BIN) -> dict[str, Any]:
    analogue = dual_resolve(name)
    invocation = invoke([name, "--version"])
    pwsh = pwsh_get_command(name)
    said_no = (
        analogue.get("win_get_command") is None
        and analogue.get("posix_which") is None
        and not invocation.get("ran")
        and pwsh.get("resolved") is None
    )
    return {
        "tool": name,
        "detector_said_no": said_no,
        "get_command_analogue": analogue,
        "invocation": {
            "ran": invocation.get("ran"),
            "exit_code": invocation.get("exit_code"),
            "error": invocation.get("error"),
        },
        "powershell_get_command_resolved": pwsh.get("resolved"),
        "powershell_shell_present": pwsh.get("shell_present"),
    }


def auth_state() -> dict[str, Any]:
    env = env_presence()
    home = gemini_home_surface()
    any_key = any(r["present"] for r in env)
    authenticated = bool(any_key or home.get("oauth_creds_present") or home.get("google_accounts"))
    return {
        "authenticated": authenticated,
        "env": env,
        "home": home,
        "note": "values never recorded; present/bytes only",
    }
