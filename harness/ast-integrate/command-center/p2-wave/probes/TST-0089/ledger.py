#!/usr/bin/env python3
"""Crash-safe JSONL run ledger for TST-0089.

A kill mid-write must not leave a truncated record visible as a complete event.
The live file is replaced atomically with a fully encoded JSONL blob under an
exclusive flock. Readers skip a trailing line that does not parse, so a torn
.tmp never becomes an event even if a crash races the replace.
"""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


LEDGER_NAME = "ledger.jsonl"
LOCK_NAME = "ledger.lock"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def ledger_path(run_dir: Path) -> Path:
    return Path(run_dir) / LEDGER_NAME


@contextmanager
def _lock(run_dir: Path) -> Iterator[None]:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(run_dir / LOCK_NAME, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def read_events(run_dir: Path) -> list[dict[str, Any]]:
    path = ledger_path(run_dir)
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    raw = path.read_text(encoding="utf-8")
    for line in raw.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            # Truncated tail: omit, do not treat as a committed event.
            break
        if isinstance(obj, dict):
            events.append(obj)
    return events


def event_types(run_dir: Path) -> list[str]:
    return [str(e.get("event") or "") for e in read_events(run_dir)]


def append_event(run_dir: Path, event: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    with _lock(run_dir):
        existing = read_events(run_dir)
        rec = dict(event)
        rec.setdefault("ts", utc_now())
        rec["seq"] = len(existing) + 1
        existing.append(rec)
        blob = "".join(json.dumps(e, ensure_ascii=True, sort_keys=True) + "\n" for e in existing)
        tmp = ledger_path(run_dir).with_suffix(".jsonl.tmp")
        tmp.write_text(blob, encoding="utf-8")
        os.replace(tmp, ledger_path(run_dir))
    return rec
