"""Load a frozen gold-set source file (bytes, sha256, text, optional JSON)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

TEXT_CAP = 200_000


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def load_source(path: Path, *, rel: str, family: str, candidate_id: str) -> dict[str, Any]:
    raw = path.read_bytes()
    sha, size = digest_bytes(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n")
    doc: Any = None
    json_ok = False
    if rel.endswith(".json"):
        try:
            doc = json.loads(text)
            json_ok = True
        except json.JSONDecodeError:
            doc = None
    return {
        "candidate_id": candidate_id,
        "family": family,
        "path": rel.replace("\\", "/"),
        "sha256": sha,
        "bytes": size,
        "text": text[:TEXT_CAP],
        "json": doc,
        "json_ok": json_ok,
    }
