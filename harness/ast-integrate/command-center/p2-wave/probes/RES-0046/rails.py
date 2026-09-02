#!/usr/bin/env python3
"""Load frozen two-rail captures and re-hash them."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE / "captures" / "index.json"
REPO = HERE.parents[3]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def capture_map(index: dict | None = None) -> dict[str, dict]:
    idx = index if index is not None else load_index()
    out: dict[str, dict] = {}
    for row in idx.get("rails") or []:
        if isinstance(row, dict) and row.get("id"):
            out[str(row["id"])] = row
    return out


def live_sha(rel_or_abs: str) -> tuple[str, int, bytes]:
    path = Path(rel_or_abs)
    if not path.is_absolute():
        path = REPO / rel_or_abs
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    return digest, len(raw.replace(b"\r\n", b"\n")), raw


def rail_record(row: dict) -> dict:
    digest, size, _ = live_sha(row["path"])
    return {
        "id": row["id"],
        "kind": row["kind"],
        "permalink": row["permalink"],
        "fetch_timestamp": row["fetch_timestamp"],
        "http_status": row["http_status"],
        "sha256": digest,
        "bytes": size,
        "path": row["path"],
    }


def text_of(row: dict) -> str:
    path = REPO / row["path"]
    return path.read_text(encoding="utf-8", errors="replace")


def needle_in(row: dict, needle: str) -> bool:
    return needle in text_of(row)
