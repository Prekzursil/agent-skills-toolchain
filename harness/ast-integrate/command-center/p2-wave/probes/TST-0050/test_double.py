"""In-process telemetry double used only by TST-0050 controls.

Not a product implementation. Live harvest excludes this directory.
"""
from __future__ import annotations

from typing import Any


def emit(enabled: bool, payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not enabled:
        return []
    return [dict(payload)]


def emit_ignores_disabled(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Negative control: a broken emitter that still sends when disabled."""
    return [dict(payload)]
