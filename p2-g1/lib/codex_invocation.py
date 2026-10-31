"""Argv-array child invocation with byte-exact argument accounting (TST-0191).

The production rule this module encodes: children are spawned with an ARGV
ARRAY, never a concatenated command string, so argument bytes survive exactly.
``echo_child_argv`` launches a real child that echoes its argv back;
``expected_hex`` computes the reference records; ``argv_bytes_match`` is plain
record equality — a diverging spawn path cannot pass it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

REPO = Path(__file__).resolve().parents[1]
ECHO_SCRIPT = REPO / "tools" / "lib" / "argv_echo.py"


def expected_hex(values: Sequence[str]) -> list[dict[str, Any]]:
    """Reference records: byte length + hex of each value's fsencoded bytes."""
    out: list[dict[str, Any]] = []
    for value in values:
        raw = os.fsencode(str(value))
        out.append({"n": len(raw), "hex": raw.hex()})
    return out


def echo_child_argv(values: Sequence[str], timeout: float = 30.0) -> list[dict[str, Any]]:
    """Spawn the echo child with an argv ARRAY (no shell) and parse its report."""
    argv = [sys.executable, "-B", str(ECHO_SCRIPT), *[str(v) for v in values]]
    try:
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    try:
        parsed = json.loads(proc.stdout.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def argv_bytes_match(values: Sequence[str], records: Any) -> bool:
    """True only when the child-reported records equal the reference exactly."""
    if not isinstance(records, list):
        return False
    return records == expected_hex(values)


__all__ = ["ECHO_SCRIPT", "argv_bytes_match", "echo_child_argv", "expected_hex"]
