"""Load captured source snapshots and confirm quote+hash rails."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE / "fixtures" / "snapshots"
META = SNAP / "_fetch_meta.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_meta() -> dict[str, dict]:
    rows = json.loads(META.read_text(encoding="utf-8"))
    return {r["name"]: r for r in rows}


def snapshot_bytes(name: str) -> bytes:
    path = SNAP / name
    if not path.is_file():
        raise FileNotFoundError(name)
    return path.read_bytes()


def haystack(name: str) -> str:
    """Searchable text: raw UTF-8 plus GitHub Contents decoded blob if present."""
    raw = snapshot_bytes(name)
    text = raw.decode("utf-8", errors="replace")
    if name.endswith(".json"):
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(doc, dict) and doc.get("encoding") == "base64" and doc.get("content"):
            blob = base64.b64decode(doc["content"])
            text += "\n" + blob.decode("utf-8", errors="replace")
    return text


def rail_record(name: str, quote: str, permalink: str) -> dict:
    meta = load_meta().get(name) or {}
    data = snapshot_bytes(name)
    hay = haystack(name)
    http = meta.get("http_status")
    return {
        "snapshot": f"command-center/p2-wave/probes/RES-0088/fixtures/snapshots/{name}",
        "permalink": permalink,
        "request_url": meta.get("request_url"),
        "fetched_at": meta.get("fetched_at"),
        "http_status": http,
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "quote": quote,
        "quote_found": quote in hay,
        "http_ok": http == 200,
    }


sha256_bytes = sha256_bytes
rail_record = rail_record
