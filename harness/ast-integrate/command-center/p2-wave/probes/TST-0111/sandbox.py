"""Execute extracted documentation commands in a declared-allowlist sandbox.

Commands not on the allowlist are not spawned. If the source also lacks an
explicit NOT-EXECUTABLE marker, the row is an unmarked exclusion (a defect),
never a silent skip.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# Declared allowlist: first-token names permitted to spawn. Everything else
# is refused unless the source doc marks the fence NOT-EXECUTABLE.
ALLOWLIST = frozenset(
    {
        "echo",
        "true",
        "false",
        "printf",
        "pwd",
        "uname",
        "date",
        "whoami",
        "basename",
        "dirname",
        "cat",
        "ls",
        "head",
        "tail",
        "wc",
        "test",
        "[",
        "python3",
        "python",
    }
)

SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")
ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def argv0(command: str) -> str | None:
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        parts = command.split()
    for part in parts:
        if ENV_ASSIGN_RE.match(part):
            continue
        name = Path(part).name
        if not name or name.startswith("-"):
            continue
        return name
    return None


def segments(command: str) -> list[str]:
    chunks = [c.strip() for c in SPLIT_RE.split(command) if c.strip()]
    return chunks or ([command.strip()] if command.strip() else [])


def allowlisted(command: str, allow: frozenset[str] | None = None) -> bool:
    names = allow or ALLOWLIST
    segs = segments(command)
    if not segs:
        return False
    for seg in segs:
        name = argv0(seg)
        if name is None or name not in names:
            return False
    return True


def _clean_env() -> dict[str, str]:
    keep = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TZ", "TERM")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NO_COLOR"] = "1"
    return env


def execute(
    command: str,
    *,
    marked_not_executable: bool,
    timeout: float = 8.0,
    allow: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Return an outcome row. Never silently omits the command."""
    names = allow or ALLOWLIST
    if not (command or "").strip():
        return {
            "outcome": "empty-fence",
            "executed": False,
            "exit_code": None,
            "stdout_head": "",
            "stderr_head": "",
            "reason": "empty-fence-body",
            "allowlisted": False,
            "marked_not_executable": marked_not_executable,
        }
    if marked_not_executable:
        return {
            "outcome": "marked-not-executable",
            "executed": False,
            "exit_code": None,
            "stdout_head": "",
            "stderr_head": "",
            "reason": "explicit-NOT-EXECUTABLE-in-source",
            "allowlisted": allowlisted(command, names),
            "marked_not_executable": True,
        }
    if not allowlisted(command, names):
        return {
            "outcome": "unmarked-not-executed",
            "executed": False,
            "exit_code": None,
            "stdout_head": "",
            "stderr_head": "",
            "reason": "not-on-declared-allowlist-and-unmarked",
            "allowlisted": False,
            "marked_not_executable": False,
        }
    sandbox = Path(tempfile.mkdtemp(prefix="tst0111-sbx-"))
    try:
        proc = subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", command],
            cwd=str(sandbox),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_clean_env(),
        )
        stdout = (proc.stdout or "")[:400]
        stderr = (proc.stderr or "")[:400]
        return {
            "outcome": "executed",
            "executed": True,
            "exit_code": int(proc.returncode),
            "stdout_head": stdout,
            "stderr_head": stderr,
            "reason": "spawned-in-allowlist-sandbox",
            "allowlisted": True,
            "marked_not_executable": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "outcome": "executed",
            "executed": True,
            "exit_code": 124,
            "stdout_head": "",
            "stderr_head": "TIMEOUT",
            "reason": "sandbox-timeout",
            "allowlisted": True,
            "marked_not_executable": False,
        }
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def other_shell_probe() -> dict[str, Any]:
    """Windows-platform specialist re-run in the other shell, if present."""
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        return {
            "ran": False,
            "shell": None,
            "verdict": "NOT-CHECKED",
            "reason": "pwsh-absent-on-this-linux-worktree",
            "exit_code": None,
        }
    try:
        proc = subprocess.run(
            [pwsh, "-NoLogo", "-NoProfile", "-Command", "echo TST-0111-OTHER-SHELL"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        ok = proc.returncode == 0 and "TST-0111-OTHER-SHELL" in (proc.stdout or "")
        return {
            "ran": True,
            "shell": pwsh,
            "verdict": "PASS" if ok else "FAIL",
            "reason": "pwsh-echo-control",
            "exit_code": int(proc.returncode),
            "stdout_head": (proc.stdout or "")[:200],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ran": True,
            "shell": pwsh,
            "verdict": "FAIL",
            "reason": type(exc).__name__,
            "exit_code": None,
        }
