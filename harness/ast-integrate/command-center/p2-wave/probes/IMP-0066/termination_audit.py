"""Reviewer grep: process-termination APIs must not appear in the guard module.

Patterns live here, not in tools/plugin/pressure_guard.py, so a grep of the
implementation is not polluted by the detector's own needle list.
"""
from __future__ import annotations

from pathlib import Path

# Blocking identifiers. A match on a non-comment line of the guard is a fail.
PATTERNS = (
    "os.kill",
    "os.killpg",
    ".kill(",
    ".terminate(",
    ".send_signal(",
    "SIGKILL",
    "SIGTERM",
    "SIGQUIT",
    "taskkill",
    "Stop-Process",
    "NtTerminateProcess",
    "pthread_kill",
    "killpg(",
    'os.system("kill',
    "os.system('kill",
    'subprocess.call(["kill"',
    "Popen.send_signal",
    "signal.pthread_kill",
    "CTRL_BREAK_EVENT",
    "CTRL_C_EVENT",
)


def hits_in(source: str) -> list[dict]:
    hits: list[dict] = []
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for pat in PATTERNS:
            if pat in line:
                hits.append(
                    {"line": i, "pattern": pat, "text": line.rstrip()[:240]}
                )
    return hits


def audit_file(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    found = hits_in(source)
    return {
        "path": str(path),
        "bytes": len(source.encode("utf-8")),
        "patterns": list(PATTERNS),
        "hits": found,
        "clean": not found,
    }
