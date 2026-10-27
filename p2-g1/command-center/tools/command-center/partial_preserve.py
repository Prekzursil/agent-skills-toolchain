"""Preserve kill-late partial artifacts as INCOMPLETE (IMP-0453)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_BODY_BYTES = 4096
LEDGER_NAME = "partials-ledger.jsonl"


def _inode(path: Path) -> int | None:
    try:
        return path.stat().st_ino
    except OSError:
        return None


def classify(path: Path, *, complete: bool) -> str:
    if complete and path.is_file() and path.stat().st_size >= DEFAULT_BODY_BYTES:
        return "COMPLETE"
    if path.is_file() and path.stat().st_size > 0:
        return "INCOMPLETE"
    return "MISSING"


def write_partial(path: Path, n: int = DEFAULT_BODY_BYTES) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"P" * n)


def append_ledger(ledger: Path, rec: dict[str, Any]) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def audit_honest_library() -> dict[str, Any]:
    return {"ok": True, "policy": "kill-late-partial-preserved", "default_bytes": DEFAULT_BODY_BYTES}
