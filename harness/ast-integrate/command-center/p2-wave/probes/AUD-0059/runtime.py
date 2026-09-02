"""Shared hook runtime: write an independent side-effect file AND a ledger row.

Two signals are required to count a fire: the dispatcher's record is not
enough, and a log line without an on-disk effect is treated as silent fire
(unproven).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def session_dir() -> Path:
    raw = os.environ.get("AUD0059_SESSION") or ""
    if not raw:
        raise RuntimeError("AUD0059_SESSION is not set")
    p = Path(raw)
    p.mkdir(parents=True, exist_ok=True)
    (p / "effects").mkdir(parents=True, exist_ok=True)
    return p


def hook_id() -> str:
    return os.environ.get("AUD0059_HOOK_ID") or "unknown"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_event() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def emit_effect(effect: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    hid = hook_id()
    sess = session_dir()
    payload = {
        "hook_id": hid,
        "effect": effect,
        "token": "AUD0059-FIRE",
        "ts": now(),
        "event": (extra or {}).get("event") or os.environ.get("AUD0059_EVENT") or "",
    }
    if extra:
        payload.update(extra)
    effect_path = sess / "effects" / f"{hid}.json"
    effect_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    row = {
        "hook_id": hid,
        "event": payload["event"],
        "fired": True,
        "status": "fired",
        "effect": effect,
        "token": "AUD0059-FIRE",
        "ts": payload["ts"],
        "effect_path": str(effect_path),
    }
    ledger = sess / "hook-ledger.jsonl"
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return payload
