"""User-visible degradation event surface.

Loud fallbacks must name the capability lost and the preserved work artifact on a
surface the user can observe (stderr DEGRADATION-EVENT lines). Debug-only traces
are SILENT by contract: they never append to USER_EVENTS.
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

_LOG = logging.getLogger("degradation_events")

USER_EVENTS: list[dict[str, Any]] = []
DEBUG_EVENTS: list[dict[str, Any]] = []


def reset() -> None:
    USER_EVENTS.clear()
    DEBUG_EVENTS.clear()


def emit_loud(
    *,
    capability_lost: str,
    fallback_kind: str,
    source: str,
    artifact_preserved: str,
    reason: str,
    **extra: Any,
) -> dict[str, Any]:
    event = {
        "type": "DEGRADATION-EVENT",
        "capability_lost": capability_lost,
        "fallback_kind": fallback_kind,
        "source": source,
        "artifact_preserved": artifact_preserved,
        "reason": reason,
        "user_visible": True,
        **extra,
    }
    USER_EVENTS.append(event)
    print("DEGRADATION-EVENT " + json.dumps(event, sort_keys=True), file=sys.stderr)
    return event


def emit_debug(
    *,
    capability_lost: str,
    fallback_kind: str,
    source: str,
    artifact_preserved: str,
    reason: str,
    **extra: Any,
) -> dict[str, Any]:
    event = {
        "type": "DEGRADATION-EVENT",
        "capability_lost": capability_lost,
        "fallback_kind": fallback_kind,
        "source": source,
        "artifact_preserved": artifact_preserved,
        "reason": reason,
        "user_visible": False,
        **extra,
    }
    DEBUG_EVENTS.append(event)
    _LOG.debug("DEGRADATION-EVENT %s", json.dumps(event, sort_keys=True))
    return event
