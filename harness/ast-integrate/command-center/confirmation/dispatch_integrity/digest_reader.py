"""Digest reader. Must not run until the gate accepts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PARSE_EVENTS: list[str] = []


def reset_parse_events() -> None:
    _PARSE_EVENTS.clear()


def parse_events() -> list[str]:
    return list(_PARSE_EVENTS)


def read_digest(root: Path, result: dict[str, Any]) -> Any:
    rel = str(
        result.get("contracted_output_path") or result.get("output_path") or ""
    ).replace("\\", "/")
    path = Path(root) / rel
    _PARSE_EVENTS.append(path.name)
    return json.loads(path.read_text(encoding="utf-8"))
