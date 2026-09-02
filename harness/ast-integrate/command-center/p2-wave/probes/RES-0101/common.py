"""Shared paths and hashing for RES-0101."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

PROBE_DIR = Path(__file__).resolve().parent
REPO = PROBE_DIR.parents[3]
UNIT_ID = "RES-0101"
OUTPUT_REL = "command-center/research/RES-0101.json"
OUTPUT_PATH = REPO / OUTPUT_REL
GOLD_PATH = PROBE_DIR / "gold_task_set.json"
INVENTORY_PATH = PROBE_DIR / "inventory.live.json"
MEASUREMENT_PATH = PROBE_DIR / "measurement.json"
SENTINEL = (
    "SUCCESS:RES-0101 in the receipt AND an accuracy-versus-catalog-size table "
    "at >=3 sizes with the pre-published gold task set attached"
)
TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
