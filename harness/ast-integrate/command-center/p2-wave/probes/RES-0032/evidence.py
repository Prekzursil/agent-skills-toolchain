#!/usr/bin/env python3
"""Load on-disk captures and INDEX.json for RES-0032 probes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAPTURES = HERE / "captures"
INDEX_PATH = CAPTURES / "INDEX.json"
ARTIFACT_REL = "command-center/research/RES-0032.json"
ALLOWED = ("public-versioned-API", "private-API", "UI-only")
SENTINEL = (
    "SUCCESS:RES-0032 in the receipt AND a platform classification table "
    "with one citation per row and at least one UI-only verdict"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_index() -> dict[str, dict]:
    rows = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("name"):
            out[str(row["name"])] = row
    return out


def capture_bytes(rel_or_name: str) -> bytes:
    path = REPO / rel_or_name if "/" in rel_or_name else CAPTURES / rel_or_name
    return path.read_bytes()


def index_row(name: str) -> dict:
    idx = load_index()
    row = idx.get(name)
    ok = row.get("ok") if row else False
    if not row or not ok:
        raise KeyError(f"capture {name} missing or not ok")
    return row


def verify_capture(name: str) -> dict:
    row = index_row(name)
    rel = str(row.get("capture_path") or "")
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    sha, size = digest_file(path)
    recorded = str(row.get("sha256") or "")
    if sha != recorded:
        raise ValueError(f"{name} sha mismatch live={sha} index={recorded}")
    return {
        "name": name,
        "url": row.get("url"),
        "fetched_at": row.get("fetched_at"),
        "http_status": int(row.get("http_status") or row.get("http_status") or 0),
        "sha256": sha,
        "bytes": size,
        "capture_path": rel,
        "final_url": row.get("final_url") or row.get("url"),
    }
