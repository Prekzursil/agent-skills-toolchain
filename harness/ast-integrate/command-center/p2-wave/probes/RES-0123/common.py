"""Shared paths and hashing for RES-0123."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/research/RES-0123.json"
OUT = REPO / OUT_REL
CAPTURES = HERE / "captures"
SENTINEL = (
    "SUCCESS:RES-0123 in the receipt AND verbatim dated clause quotes per rail "
    "plus an explicit list of conflicts with current practice"
)
UNIT = "RES-0123"


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump(path: Path, doc: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
