"""PR-ONLY publishing guard (IMP-0112). Outbound publish lives only here."""
from __future__ import annotations

from typing import Any

from release_mode import BINDING_MODE, PUBLIC_MODE, load_mode

BLOCKED_NEEDS_OWNER = "BLOCKED-NEEDS-OWNER"
PROCEEDED = "PROCEEDED"
PUBLISHING_ENTRY_POINTS = (
    "publish",
    "yank",
    "promote",
    "sync_index",
)

_LOG: list[dict[str, Any]] = []


def reset_outbound_log() -> None:
    _LOG.clear()


def outbound_log() -> list[dict[str, Any]]:
    return list(_LOG)


def record(event: dict[str, Any]) -> None:
    _LOG.append(dict(event))


def _outbound_publish(pkg: str, *, sink: str = "_outbound_publish") -> dict[str, Any]:
    rec = {"pkg": pkg, "sink": sink}
    _LOG.append(rec)
    return rec


def gate(
    entry_point: str,
    payload: dict[str, Any] | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    mode = load_mode(config_path)
    if mode == BINDING_MODE:
        return {
            "status": BLOCKED_NEEDS_OWNER,
            "code": BLOCKED_NEEDS_OWNER,
            "release_mode": mode,
            "owner_approval_request": {"required": True, "entry_point": entry_point},
            "side_effects": {"network": False, "recorded_outbound": False},
            "entry_point": entry_point,
        }
    outbound = _outbound_publish(str(payload.get("pkg") or entry_point))
    return {
        "status": PROCEEDED,
        "code": PROCEEDED,
        "release_mode": PUBLIC_MODE,
        "owner_approval_request": {"required": False},
        "side_effects": {"network": True, "recorded_outbound": True},
        "outbound": outbound,
        "entry_point": entry_point,
    }
