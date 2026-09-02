#!/usr/bin/env python3
"""Confirmation cost from the event log, never from confirmer self-report.

CNF-0144 tests_required: 'Cost measurement independence: durations must come
from the event log, not from the confirmer's self-report.'
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Keys that look like a confirmer self-report. extract_costs() must not read
# these off confirmation records. The planted records in fixtures/ deliberately
# invert wall-clock so a fallback would reverse the convenience-bias sign.
SELF_REPORT_KEYS = frozenset(
    {
        "cost",
        "duration",
        "duration_seconds",
        "elapsed",
        "elapsed_seconds",
        "self_reported_seconds",
        "self_reported_tool_count",
        "self_reported_wall_clock",
        "tool_count",
        "wall_clock",
        "wall_clock_seconds",
    }
)


@dataclass(frozen=True)
class EventCost:
    claim_id: str
    dispatch_ts: datetime | None
    completion_ts: datetime | None
    wall_clock_seconds: float | None
    substrate: str | None
    tool_count: int
    source: str = "event-log"


def parse_ts(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iter_events(path: Path) -> Iterable[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(raw.splitlines(), 1):
        text = line.strip()
        if not text:
            continue
        try:
            rec = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"torn event log {path}:{line_no}: {exc}") from exc
        if not isinstance(rec, dict):
            raise ValueError(f"non-object event {path}:{line_no}")
        yield rec


def load_event_costs(events_path: Path) -> dict[str, EventCost]:
    """Parse dispatch, tool_call, and completion events into per-claim costs."""
    dispatch: dict[str, datetime] = {}
    completion: dict[str, datetime] = {}
    substrate: dict[str, str] = {}
    tools: dict[str, int] = {}
    for rec in iter_events(events_path):
        kind = str(rec.get("event") or rec.get("type") or "")
        claim_id = str(rec.get("claim_id") or "")
        if not claim_id:
            continue
        ts_raw = rec.get("ts") or rec.get("timestamp")
        ts = parse_ts(str(ts_raw)) if ts_raw else None
        if kind == "dispatch":
            if ts is not None:
                dispatch[claim_id] = ts
            sub = rec.get("substrate")
            if isinstance(sub, str) and sub:
                substrate[claim_id] = sub
        elif kind in {"tool_call", "tool"}:
            tools[claim_id] = tools.get(claim_id, 0) + 1
        elif kind in {"completion", "complete", "completed"}:
            if ts is not None:
                completion[claim_id] = ts
    claim_ids = set(dispatch) | set(completion) | set(tools)
    out: dict[str, EventCost] = {}
    for cid in sorted(claim_ids):
        d = dispatch.get(cid)
        c = completion.get(cid)
        wall = None
        if d is not None and c is not None:
            wall = (c - d).total_seconds()
        out[cid] = EventCost(
            claim_id=cid,
            dispatch_ts=d,
            completion_ts=c,
            wall_clock_seconds=wall,
            substrate=substrate.get(cid),
            tool_count=int(tools.get(cid, 0)),
        )
    return out


def record_self_report_seconds(record: dict[str, Any]) -> float | None:
    """Expose self-report ONLY for the independence control. Detector never calls this."""
    for key in (
        "self_reported_seconds",
        "self_reported_wall_clock",
        "duration_seconds",
        "wall_clock_seconds",
        "duration",
    ):
        val = record.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def extract_costs(
    events_path: Path,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, EventCost]:
    """Return event-log costs. `records` is accepted and ignored for duration.

    Passing confirmation records must not change a single wall_clock_seconds
    value. That is the independence invariant.
    """
    del records  # duration independence: confirmer documents are not a cost source
    return load_event_costs(events_path)
