"""Load RES-0116 capture index and verify on-disk sha256."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"
INDEX = CAP / "_index.json"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_index() -> list[dict]:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def by_id() -> dict[str, dict]:
    return {row["id"]: row for row in load_index()}


def capture_bytes(cid: str) -> bytes:
    path = CAP / f"{cid}.bin"
    return path.read_bytes()


def capture_text(cid: str) -> str:
    return capture_bytes(cid).decode("utf-8", errors="replace")


def verify_row(row: dict) -> tuple[bool, str]:
    cid = row["id"]
    path = CAP / f"{cid}.bin"
    if not path.is_file():
        return False, f"missing {cid}.bin"
    raw = path.read_bytes()
    live = sha256_bytes(raw)
    recorded = row.get("sha256")
    if recorded and recorded != live:
        return False, f"sha mismatch {cid}"
    if int(row.get("byte_length") or -1) != len(raw):
        return False, f"length mismatch {cid}"
    return True, live
