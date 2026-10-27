"""Engineering blueprint event ledger reader. TST-0055."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_events(path: str | Path) -> Any:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    try:
        row = json.loads(text)
        return row
    except json.JSONDecodeError:
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rows.append(row)
        return rows
