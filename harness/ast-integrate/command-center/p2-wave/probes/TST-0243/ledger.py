#!/usr/bin/env python3
"""Harvest a run ledger of per-unit wall-clock durations.

Primary live source: /opt/p2/supervisor.log (LAUNCH paired with DONE-OK).
A JSONL snapshot is written under captures/ so the join can re-run without
re-eyeballing the log.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from join import UID_RE, unit_class

HERE = Path(__file__).resolve().parent
DEFAULT_LOG = Path("/opt/p2/supervisor.log")
SNAPSHOT = HERE / "captures" / "run-ledger.jsonl"

LAUNCH_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) LAUNCH ([A-Z]{2,5}-\d{4})\b"
)
DONE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) DONE-OK ([A-Z]{2,5}-\d{4})\b"
)


def parse_ts(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def supervisor_log_path() -> Path | None:
    env = os.environ.get("TST_0243_SUPERVISOR_LOG")
    if env:
        p = Path(env)
        return p if p.is_file() else None
    if DEFAULT_LOG.is_file():
        return DEFAULT_LOG
    return None


def harvest_supervisor(log_path: Path) -> list[dict[str, Any]]:
    last_launch: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        m = LAUNCH_RE.match(line)
        if m:
            last_launch[m.group(2)] = m.group(1)
            continue
        m = DONE_RE.match(line)
        if not m:
            continue
        ts_done, uid = m.group(1), m.group(2)
        if not UID_RE.match(uid):
            continue
        ts_launch = last_launch.get(uid)
        if not ts_launch:
            continue
        t0 = parse_ts(ts_launch)
        t1 = parse_ts(ts_done)
        dur = (t1 - t0).total_seconds()
        if dur < 0:
            continue
        rows.append(
            {
                "unit_id": uid,
                "class": unit_class(uid),
                "t_launch": ts_launch,
                "t_done": ts_done,
                "duration_seconds": dur,
                "source": str(log_path),
            }
        )
    return rows


def load_snapshot(path: Path = SNAPSHOT) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if isinstance(rec, dict) and rec.get("unit_id"):
            rows.append(rec)
    return rows


def write_snapshot(rows: list[dict[str, Any]], path: Path = SNAPSHOT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    path.write_text(body, encoding="utf-8")
    return path


def harvest(write: bool = True) -> dict[str, Any]:
    log_path = supervisor_log_path()
    source = "supervisor-log" if log_path is not None else "snapshot"
    if log_path is not None:
        rows = harvest_supervisor(log_path)
        if write:
            write_snapshot(rows)
    else:
        rows = load_snapshot()
        source = "snapshot-fallback"
    by_class: dict[str, list[float]] = defaultdict(list)
    for rec in rows:
        by_class[str(rec["class"])].append(float(rec["duration_seconds"]))
    return {
        "source": source,
        "log_path": str(log_path) if log_path is not None else None,
        "snapshot_path": str(SNAPSHOT.relative_to(HERE.parents[3]))
        if SNAPSHOT.is_file()
        else None,
        "n_records": len(rows),
        "n_classes_with_samples": len(by_class),
        "records": rows,
        "durations_by_class": {k: v for k, v in sorted(by_class.items())},
    }
