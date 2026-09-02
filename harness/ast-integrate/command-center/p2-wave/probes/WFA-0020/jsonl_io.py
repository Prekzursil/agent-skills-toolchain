"""JSONL helpers. Invalid lines are counted, never executed."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    bad = 0
    if not path.is_file():
        return rows, bad
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        else:
            bad += 1
    return rows, bad
