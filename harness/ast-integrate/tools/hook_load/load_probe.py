"""Strict hook-config loader: unknown fields are refused by name (TST-0052)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KNOWN_KEYS = frozenset(
    {
        "hooks",
        "commands",
        "matcher",
        "type",
        "command",
        "timeout",
        "enabled",
        "name",
        "version",
        "description",
        "event",
        "script",
    }
)


class LoadRefusal(ValueError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


def _refuse_unknown(doc: Any, path: str = "") -> None:
    if isinstance(doc, dict):
        for key, val in doc.items():
            if key not in KNOWN_KEYS and not str(key).startswith("$"):
                loc = f"{path}.{key}" if path else key
                raise LoadRefusal(f"unknown field {key}", field=key)
            _refuse_unknown(val, f"{path}.{key}" if path else key)
    elif isinstance(doc, list):
        for item in doc:
            _refuse_unknown(item, path)


def load_config(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        raise LoadRefusal("hooks config must be an object")
    _refuse_unknown(doc)
    return doc


__all__ = ["LoadRefusal", "load_config"]
