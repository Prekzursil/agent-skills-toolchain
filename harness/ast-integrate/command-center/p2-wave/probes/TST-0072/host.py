#!/usr/bin/env python3
"""Read-only host fingerprint. Rollback rehearsal must not touch the live host."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parents[3]


def _fp(path: Path) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "is_file": path.is_file(),
    }
    if path.is_file():
        data = path.read_bytes()
        rec["sha256"] = hashlib.sha256(data).hexdigest()
        rec["bytes"] = len(data)
    elif path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.is_file())
        rec["file_count"] = len(files)
        h = hashlib.sha256()
        for p in files[:200]:
            rel = p.relative_to(path).as_posix().encode("utf-8")
            body = p.read_bytes()
            h.update(rel)
            h.update(b"\0")
            h.update(body)
            h.update(b"\n")
        rec["tree_sha256"] = h.hexdigest()
    return rec


def host_census() -> dict[str, Any]:
    home = Path.home()
    # Do not hash ~/.cursor (this session writes agent state there).
    rows = [
        _fp(REPO / "rules"),
        _fp(home / ".claude"),
        _fp(home / ".claude" / "rules"),
        _fp(home / ".cursor" / "rules"),
        _fp(home / ".claude"),
        _fp(home / ".claude" / "rules"),
        _fp(home / ".cursor" / "rules"),
    ]
    return {
        "rows": rows,
        "note": "read-only; TST-0072 rehearsal uses tempfile only",
    }
