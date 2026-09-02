#!/usr/bin/env python3
"""Run the live client with/without a candidate and record a behaviour delta."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from pathlib import Path

SECRET_RE = re.compile(
    r"(key|token|secret|authorization)([\"':=\s]+)([^\s\"']{8,})",
    re.IGNORECASE,
)


def redact(text: str) -> str:
    text = SECRET_RE.sub(r"\1\2[REDACTED]", text or "")
    # Never keep a live API key shape.
    text = re.sub(r"\bkey_[A-Za-z0-9]{16,}\b", "[REDACTED_KEY]", text)
    return text


def fingerprint(stdout: str, stderr: str, rc: int) -> str:
    blob = f"rc={rc}\nSTDOUT\n{stdout}\nSTDERR\n{stderr}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def run_cmd(
    argv: list[str],
    env: dict[str, str] | None,
    timeout: float = 20.0,
    cwd: str | None = None,
) -> dict:
    # Callers that pass `env` supply the full child environment (already copied
    # and mutated). `update()` would not delete popped keys.
    merged = os.environ.copy() if env is None else dict(env)
    try:
        p = subprocess.run(
            argv,
            cwd=cwd,
            env=merged,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        rc = p.returncode
        out = redact(p.stdout or "")
        err = redact(p.stderr or "")
    except subprocess.TimeoutExpired as exc:
        rc = 124
        out = redact((exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, (bytes, bytearray)) else (exc.stdout or ""))
        err = "TIMEOUT"
    except OSError as exc:
        rc = 127
        out = ""
        err = redact(str(exc))
    return {
        "argv": argv,
        "rc": rc,
        "stdout": out[-4000:],
        "stderr": err[-4000:],
        "fingerprint": fingerprint(out, err, rc),
        "stdout_len": len(out),
        "stderr_len": len(err),
    }


def env_without(*names: str) -> dict[str, str]:
    merged = os.environ.copy()
    for n in names:
        merged.pop(n, None)
    return merged


def compare_runs(off: dict, on: dict) -> dict:
    delta = off["fingerprint"] != on["fingerprint"]
    reasons = []
    if off["rc"] != on["rc"]:
        reasons.append(f"exit {off['rc']} -> {on['rc']}")
    if off["stdout"] != on["stdout"]:
        reasons.append("stdout changed")
    if off["stderr"] != on["stderr"]:
        reasons.append("stderr changed")
    return {
        "delta": delta,
        "reasons": reasons,
        "off_fp": off["fingerprint"],
        "on_fp": on["fingerprint"],
        "off_rc": off["rc"],
        "on_rc": on["rc"],
    }


def scratch_dir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))
