"""Runtime JSON scanner patterns (TST-0341)."""
from __future__ import annotations

import json
from pathlib import Path

FORBIDDEN_PATTERNS = ("AKIA", "ghp_", "xoxb-")


def scan_json_file(path: str | Path) -> dict:
    p = Path(path)
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    hits = [pat for pat in FORBIDDEN_PATTERNS if pat in text]
    return {"path": str(p), "hits": hits}
