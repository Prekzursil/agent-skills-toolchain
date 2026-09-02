"""Runtime probe: each contracted event must have produced its own side effect.

Silent = every event observed. Fires = at least one contracted event missing.
A missing side effect is NOT-CHECKED in the receipt, never PASS.
"""
from __future__ import annotations

import json
from pathlib import Path

from package_spec import CONTRACTED_EVENTS, EFFECTS_DIRNAME


def observe_event(profile: Path, event: str, nonce: str | None = None) -> dict:
    path = profile / EFFECTS_DIRNAME / f"{event}.json"
    if not path.is_file():
        return {
            "event": event,
            "observed": False,
            "side_effect_path": None,
            "timestamp": None,
            "verdict": "NOT-CHECKED",
            "why": "side-effect-file-absent",
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "event": event,
            "observed": False,
            "side_effect_path": str(path),
            "timestamp": None,
            "verdict": "NOT-CHECKED",
            "why": f"unparseable:{type(exc).__name__}",
        }
    if data.get("event") != event:
        return {
            "event": event,
            "observed": False,
            "side_effect_path": str(path),
            "timestamp": data.get("ts_utc"),
            "verdict": "NOT-CHECKED",
            "why": "event-field-mismatch",
        }
    if nonce is not None and data.get("nonce") != nonce:
        return {
            "event": event,
            "observed": False,
            "side_effect_path": str(path),
            "timestamp": data.get("ts_utc"),
            "verdict": "NOT-CHECKED",
            "why": "nonce-mismatch-stale-or-foreign-effect",
        }
    return {
        "event": event,
        "observed": True,
        "pid": data.get("pid"),
        "side_effect_path": str(path),
        "timestamp": data.get("ts_utc"),
        "ts_ns": data.get("ts_ns"),
        "verdict": "PASS",
        "why": "runtime-side-effect-observed",
    }


def probe(profile: Path, nonce: str | None = None, events: tuple[str, ...] = CONTRACTED_EVENTS) -> dict:
    rows = [observe_event(profile, event, nonce=nonce) for event in events]
    missing = [r["event"] for r in rows if not r["observed"]]
    return {
        "events": rows,
        "fired": bool(missing),
        "missing": missing,
        "observed_count": sum(1 for r in rows if r["observed"]),
        "silent": not missing,
        "total": len(rows),
    }
