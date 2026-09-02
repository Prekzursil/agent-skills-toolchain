"""Load captured rails and recompute sha256 of on-disk bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from constants import CAPTURE_REL

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAPTURES = REPO / CAPTURE_REL


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_index() -> dict:
    path = CAPTURES / "_index.json"
    return json.loads(path.read_text(encoding="utf-8"))


def rails_by_file() -> dict[str, dict]:
    idx = load_index()
    out = {}
    for rec in idx.get("rails") or []:
        if isinstance(rec, dict) and rec.get("file"):
            out[str(rec["file"])] = rec
    return out


def live_capture(fname: str) -> dict:
    rec = rails_by_file()[fname]
    path = CAPTURES / fname
    raw = path.read_bytes()
    live = digest_bytes(raw)
    return {
        "file": fname,
        "path": f"{CAPTURE_REL}/{fname}",
        "permalink": rec.get("final_url") or rec.get("permalink"),
        "fetch_timestamp": rec.get("fetch_timestamp"),
        "http_status": rec.get("http_status"),
        "sha256": rec.get("sha256"),
        "live_sha256": live,
        "bytes": len(raw),
        "sha_match": live == rec.get("sha256"),
        "content_type": rec.get("content_type"),
        "error": rec.get("error"),
    }


def rail(
    kind: str,
    fname: str,
    snippet: str,
    anchors: list[str],
    note: str | None = None,
) -> dict:
    cap = live_capture(fname)
    if not cap["sha_match"]:
        raise RuntimeError(f"capture hash drift {fname}")
    status = cap["http_status"]
    if not isinstance(status, int) or status >= 400 or cap["bytes"] <= 0:
        raise RuntimeError(f"unusable capture {fname} status={status} bytes={cap['bytes']}")
    body = read_text(fname)
    missing = [a for a in anchors if a not in body]
    if missing:
        raise RuntimeError(f"anchors missing from {fname}: {missing}")
    row = {
        "kind": kind,
        "permalink": cap["permalink"],
        "fetch_timestamp": cap["fetch_timestamp"],
        "http_status": status,
        "sha256": cap["sha256"],
        "captured_bytes": cap["bytes"],
        "capture_path": cap["path"],
        "snippet": snippet,
        "anchors": anchors,
    }
    if note:
        row["note"] = note
    return row


def read_text(fname: str) -> str:
    return (CAPTURES / fname).read_text(encoding="utf-8", errors="replace")


def read_json(fname: str):
    return json.loads((CAPTURES / fname).read_text(encoding="utf-8"))
