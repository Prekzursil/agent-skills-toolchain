"""Count observed invocations from the usage ledger (jsonl)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

AS_OF = datetime(2026, 8, 24, tzinfo=timezone.utc)
WINDOW_DAYS = 14


def parse_ts(raw: str) -> datetime:
    text = raw.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if not isinstance(rec, dict) or not rec.get("name") or not rec.get("ts"):
            raise ValueError(f"bad ledger line {i}")
        events.append(rec)
    return events


def counts_in_window(
    events: list[dict[str, Any]],
    *,
    as_of: datetime = AS_OF,
    window_days: int = WINDOW_DAYS,
) -> dict[str, int]:
    start = as_of - timedelta(days=window_days)
    out: dict[str, int] = {}
    for rec in events:
        ts = parse_ts(str(rec["ts"]))
        if start <= ts <= as_of:
            name = str(rec["name"])
            out[name] = out.get(name, 0) + 1
    return out
