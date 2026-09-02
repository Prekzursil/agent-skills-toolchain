"""CLI exit-code contract: one integer per failure class."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

SUCCESS = 0
USAGE_ERROR = 2
PRECONDITION_FAILED = 10
VALIDATION_FAILED = 11
PERMISSION_DENIED = 12
BLOCKED_NEEDS_OWNER = 13
INTERNAL_ERROR = 14

BY_NAME = {
    "SUCCESS": SUCCESS,
    "USAGE_ERROR": USAGE_ERROR,
    "PRECONDITION_FAILED": PRECONDITION_FAILED,
    "VALIDATION_FAILED": VALIDATION_FAILED,
    "PERMISSION_DENIED": PERMISSION_DENIED,
    "BLOCKED_NEEDS_OWNER": BLOCKED_NEEDS_OWNER,
    "INTERNAL_ERROR": INTERNAL_ERROR,
}
CONTRACT = dict(BY_NAME)
DOCUMENTATION = (
    "0 success only when verify succeeds; 2 usage; 10 precondition; "
    "11 validation; 12 permission; 13 owner gate; 14 internal"
)

_SHELL_RESERVED = frozenset({1, 126, 127, 128, 129, 130, 137, 139, 143, 255})

PERM_DENIED_PATH = "/sys/imp0055-denied"


def names() -> dict[str, int]:
    return dict(BY_NAME)


def is_shell_reserved(code: int | str) -> bool:
    if isinstance(code, str):
        if code in BY_NAME:
            code = BY_NAME[code]
        else:
            try:
                code = int(code)
            except ValueError:
                return False
    return int(code) in _SHELL_RESERVED


def cli_argv(*args: str) -> list[str]:
    cli = Path(__file__).resolve().parent / "cli.py"
    return [sys.executable, "-B", str(cli), *args]


@dataclass
class Observed:
    present: bool
    exit_code: int | None
    stdout: str
    stderr: str
    error: str | None = None
    stdout_tail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "exit_code": self.exit_code,
            "stdout_tail": (self.stdout_tail or self.stdout)[-400:],
            "stderr": (self.stderr or "")[-400:],
            "error": self.error,
        }


def observe_argv(argv: Sequence[str], via: str = "native") -> Observed:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        if via == "native":
            p = subprocess.run(list(argv), capture_output=True, text=True, timeout=30, env=env)
        elif via == "bash":
            bash = shutil.which("bash")
            if not bash:
                return Observed(False, None, "", "", error="bash-absent")
            inner = " ".join(_shlex_quote(a) for a in argv) + "; exit $?"
            p = subprocess.run(
                [bash, "-lc", inner],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
        elif via in {"pwsh7", "pwsh"}:
            pwsh = shutil.which("pwsh")
            if pwsh and os.name != "nt" and pwsh.endswith(".exe"):
                pwsh = None
            if pwsh is None and os.name == "nt":
                pwsh = shutil.which("pwsh.exe")
            if not pwsh:
                return Observed(False, None, "", "", error="pwsh-absent")
            # Call operator so native $LASTEXITCODE is the child python exit.
            script = (
                "& "
                + " ".join(_ps_quote(a) for a in argv)
                + "; exit $LASTEXITCODE"
            )
            p = subprocess.run(
                [pwsh, "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=40,
                env=env,
            )
        else:
            p = subprocess.run(list(argv), capture_output=True, text=True, timeout=30, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Observed(False, None, "", "", error=f"{type(exc).__name__}:{exc}")
    return Observed(
        present=True,
        exit_code=p.returncode,
        stdout=p.stdout or "",
        stderr=p.stderr or "",
        stdout_tail=(p.stdout or "")[-800:],
    )


def _shlex_quote(s: str) -> str:
    import shlex

    return shlex.quote(s)


def _ps_quote(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def verify_contract() -> dict[str, Any]:
    values = list(BY_NAME.values())
    reserved = [c for c in values if is_shell_reserved(c)]
    unique = len(values) == len(set(values))
    return {
        "verified": unique and not reserved and SUCCESS == 0 and USAGE_ERROR != 0,
        "unique": unique,
        "reserved_collisions": reserved,
        "by_name": dict(BY_NAME),
    }
