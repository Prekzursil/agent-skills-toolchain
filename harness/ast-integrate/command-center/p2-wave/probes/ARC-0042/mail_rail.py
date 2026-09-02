"""Old agent-mail peer channel: in-process JSON envelope.

No live listener on 127.0.0.1:8765/8812 is assumed (AUD-0066 recorded the
declared peer down). The working rail is the message shape + protected name
'agent-mail', not a spawned server.
"""
from __future__ import annotations

from typing import Any, Mapping


def old_artifact(unit: Mapping[str, Any]) -> dict[str, Any]:
    uid = str(unit.get("id") or "")
    sentinel = str(unit.get("completion_sentinel") or "")
    body = {
        "kind": "peer-receipt",
        "unit_id": uid,
        "sentinel": sentinel,
        "output_path": unit.get("output_path"),
        "protected_service": "agent-mail",
    }
    return {
        "unit_id": uid,
        "sentinel": sentinel,
        "body": body,
        "mailbox": "agent-mail",
        "peer_channel": "http+json",
        "peer_route": "/peer/receipt",
    }
