#!/usr/bin/env python3
"""Line:snippet anchors that must resolve on the live tree."""
from __future__ import annotations

from pathlib import Path

import inventory as I


def line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise RuntimeError(f"anchor needle not found in {path}: {needle!r}")


def resolve(repo: Path, rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = repo / rel
    if not path.is_file():
        return False, f"missing {rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"{rel}:{line} oob"
    body = lines[line - 1]
    if snippet not in body:
        return False, f"{rel}:{line} snippet-miss"
    return True, f"{rel}:{line}"


def evidence_plan() -> list[dict]:
    consumer = I.HERE / "consumer.py"
    harness = I.HERE / "harness.py"
    return [
        {
            "claim": "Fixture credential denial is implemented as an unset variable, not a file edit",
            "verdict": "CONFIRMED",
            "anchor": f"command-center/p2-wave/probes/CNF-0117/harness.py:{line_of(harness, 'env.pop(I.TOKEN_ENV, None)')}",
            "snippet": "env.pop(I.TOKEN_ENV, None)",
            "path": "command-center/p2-wave/probes/CNF-0117/harness.py",
            "line": line_of(harness, "env.pop(I.TOKEN_ENV, None)"),
        },
        {
            "claim": "Missing fixture token is a loud failure that names credential:CNF_0117_TOKEN",
            "verdict": "CONFIRMED",
            "anchor": f"command-center/p2-wave/probes/CNF-0117/consumer.py:{line_of(consumer, 'FAILED:missing-capability credential:')}",
            "snippet": "FAILED:missing-capability credential:",
            "path": "command-center/p2-wave/probes/CNF-0117/consumer.py",
            "line": line_of(consumer, "FAILED:missing-capability credential:"),
        },
        {
            "claim": "Enrichment-write denial marks the produced artifact degraded in its own body",
            "verdict": "CONFIRMED",
            "anchor": f"command-center/p2-wave/probes/CNF-0117/consumer.py:{line_of(consumer, '\"degraded\": degraded')}",
            "snippet": '"degraded": degraded',
            "path": "command-center/p2-wave/probes/CNF-0117/consumer.py",
            "line": line_of(consumer, '"degraded": degraded'),
        },
        {
            "claim": "dispatch_cursor.py fails loud when CURSOR_API_KEY is unset, naming the variable",
            "verdict": "CONFIRMED",
            "anchor": f"command-center/p2-wave/seed-stage/dispatch_cursor.py:{line_of(I.DISPATCH, 'FAILED:no CURSOR_API_KEY in env')}",
            "snippet": "FAILED:no CURSOR_API_KEY in env",
            "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
            "line": line_of(I.DISPATCH, "FAILED:no CURSOR_API_KEY in env"),
        },
    ]
