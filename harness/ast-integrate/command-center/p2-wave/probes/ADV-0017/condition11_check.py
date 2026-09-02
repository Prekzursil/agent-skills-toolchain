#!/usr/bin/env python3
"""Condition 11: per-unit UNIT-ARTIFACT-MANIFEST.json row matches live artifact."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from audit_common import OUT_REL, REPO, UID


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def check_manifest(man_path: Path) -> dict:
    man = json.loads(man_path.read_text(encoding="utf-8"))
    out = REPO / OUT_REL
    if not out.is_file() or out.stat().st_size <= 0:
        return {"ok": False, "reason": "artifact-absent"}
    live_sha, live_bytes = digest_file(out)
    rows = [
        a
        for a in (man.get("artifacts") or [])
        if isinstance(a, dict) and a.get("unit_id") == UID
    ]
    matching = [
        a
        for a in rows
        if str(a.get("path") or "").replace("\\", "/") == OUT_REL
        and str(a.get("sha256") or "") == live_sha
        and a.get("present") is True
    ]
    return {
        "ok": bool(matching),
        "live_sha256": live_sha,
        "live_bytes": live_bytes,
        "matching": len(matching),
        "reason": None if matching else "manifest-sha-mismatch",
    }
