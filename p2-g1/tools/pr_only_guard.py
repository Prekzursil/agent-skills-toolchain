"""PR-only outbound log used by TST-0199."""
from __future__ import annotations

from typing import Any

_LOG: list[dict[str, Any]] = []


def reset_outbound_log() -> None:
    _LOG.clear()


def outbound_log() -> list[dict[str, Any]]:
    return list(_LOG)


def record(event: dict[str, Any]) -> None:
    _LOG.append(dict(event))
