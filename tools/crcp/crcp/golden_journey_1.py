#!/usr/bin/env python3
"""Run CRCP golden journey 1 entirely from deterministic local fixtures."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from .envelope_v11 import require_valid
from .event_spool import EventSpool, make_event_key, payload_sha256


_PKG = Path(__file__).resolve().parent
_ROOT = _PKG.parent
FIXTURE_DIR = (
    (_ROOT / "fixtures" / "dbx" / "golden_journey_1")
    if (_ROOT / "fixtures" / "dbx" / "golden_journey_1").is_dir()
    else (_PKG / "fixtures" / "golden_journey_1")
)
DELTA_PATH = FIXTURE_DIR / "chatgpt_delta.json"
EXPECTED_PATH = FIXTURE_DIR / "expected_task_request.json"


def load_object(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object with an actionable fixture error."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load fixture {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"fixture must contain a JSON object: {path}")
    return value


def _required_string(source: dict[str, Any], field: str) -> str:
    value = source.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"delta field {field!r} must be a non-empty string")
    return value


def build_task_request(delta: dict[str, Any]) -> dict[str, Any]:
    """Convert a minimal ChatGPT delta to a deterministic task.request."""
    conversation_id = _required_string(delta, "conversation_id")
    update_time = _required_string(delta, "update_time")
    messages = delta.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("delta field 'messages' must be a non-empty list")

    digest = payload_sha256(delta)
    envelope: dict[str, Any] = {
        "schema": "crcp.envelope.v1.1",
        "id": "00000000-0000-4000-8000-000000000101",
        "created_at": "2026-07-20T12:00:01+00:00",
        "event_key": make_event_key(conversation_id, update_time, delta),
        "trace_id": "00000000-0000-4000-8000-000000000100",
        "kind": "task.request",
        "from_rail": "chatgpt_live_bridge",
        "to_rail": "orchestrator",
        "intent": "execute",
        "payload_ref": f"sha256:{digest}",
        "capabilities_required": ["orchestrate"],
        "completion": "PENDING",
        "meta": {
            "source": "fixture",
            "conversation_id": conversation_id,
            "update_time": update_time,
        },
    }
    require_valid(envelope)
    return envelope


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run() -> dict[str, Any]:
    """Execute deterministic construction, replay, and duplicate-effect checks."""
    delta = load_object(DELTA_PATH)
    expected = load_object(EXPECTED_PATH)
    first = build_task_request(delta)
    replay = build_task_request(load_object(DELTA_PATH))

    _check(first["event_key"] == replay["event_key"], "event_key changed on replay")
    _check(first == expected, "built task.request does not match golden fixture")

    logical_effects: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="crcp-golden-journey-1-") as directory:
        with EventSpool(Path(directory) / "events.sqlite3") as spool:
            if spool.observe(first["event_key"], first):
                logical_effects.add(first["event_key"])
            if spool.observe(replay["event_key"], replay):
                logical_effects.add(replay["event_key"])

            _check(spool.count() == 1, "duplicate created more than one spool record")
            _check(
                len(logical_effects) == 1,
                "duplicate caused more than one logical effect",
            )
            spool.transition(first["event_key"], "spooled")
            spool.transition(first["event_key"], "publishing")
            spool.transition(first["event_key"], "acked")
            _check(
                spool.state(first["event_key"]) == "acked", "spool did not reach acked"
            )

    return {
        "status": "PASS",
        "kind": first["kind"],
        "event_key": first["event_key"],
        "logical_effects": len(logical_effects),
    }


def main() -> int:
    try:
        result = run()
    except Exception as exc:
        print(f"golden_journey_1: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
