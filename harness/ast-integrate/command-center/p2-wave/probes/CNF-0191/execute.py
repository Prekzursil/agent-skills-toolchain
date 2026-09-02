"""Execute a documented command only after the refusal list is applied."""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from extract import Extracted
from refuse import Refusal, classify, redact

# Commands actually handed to bash. Probe2 asserts refused strings are absent.
SUBPROCESS_LOG: list[str] = []


@dataclass
class Outcome:
    path: str
    line: int
    command: str
    command_redacted: str
    documented_output: str
    outcome: str  # PASS FAIL DIFF NOT-CHECKED
    exit_code: int | None
    stdout: str
    stderr: str
    output_diff: str
    refused_before_exec: bool
    refusal: Refusal | None = None
    subprocess_attempted: bool = False


def _diff(got: str, want: str) -> str:
    g = (got or "").replace("\r\n", "\n").rstrip("\n")
    w = (want or "").replace("\r\n", "\n").rstrip("\n")
    if g == w:
        return ""
    return f"got={g!r} documented={w!r}"


def _run_bash(cmd: str, workdir: str, env: dict, timeout: float) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["bash", "-c", cmd],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", f"TIMEOUT after {timeout}s"
    except OSError as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"


def execute_one(
    row: Extracted,
    *,
    timeout: float = 20.0,
    cwd: Path | None = None,
) -> Outcome:
    cmd = row.command
    shown = redact(cmd)
    refusal = classify(cmd)
    if refusal is not None:
        return Outcome(
            path=row.path,
            line=row.line,
            command=shown,
            command_redacted=shown,
            documented_output=row.documented_output,
            outcome="NOT-CHECKED",
            exit_code=None,
            stdout="",
            stderr="",
            output_diff="",
            refused_before_exec=True,
            refusal=refusal,
            subprocess_attempted=False,
        )
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    SUBPROCESS_LOG.append(cmd)
    if cwd is not None:
        code, stdout, stderr = _run_bash(cmd, str(cwd), env, timeout)
    else:
        with tempfile.TemporaryDirectory(prefix="cnf0191-") as tmp:
            code, stdout, stderr = _run_bash(cmd, tmp, env, timeout)
    documented = row.documented_output
    delta = _diff(stdout, documented) if documented else ""
    if code != 0:
        kind = "FAIL"
    elif documented and delta:
        kind = "DIFF"
    else:
        kind = "PASS"
    return Outcome(
        path=row.path,
        line=row.line,
        command=shown,
        command_redacted=shown,
        documented_output=documented,
        outcome=kind,
        exit_code=code,
        stdout=stdout[-4000:],
        stderr=stderr[-4000:],
        output_diff=delta,
        refused_before_exec=False,
        refusal=None,
        subprocess_attempted=True,
    )


def execute_rows(
    rows: list[Extracted],
    *,
    timeout: float = 20.0,
    cwd: Path | None = None,
) -> list[Outcome]:
    return [execute_one(r, timeout=timeout, cwd=cwd) for r in rows]


def reset_subprocess_log() -> None:
    SUBPROCESS_LOG.clear()
