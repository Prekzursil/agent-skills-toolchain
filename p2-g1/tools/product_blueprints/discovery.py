"""Product-discovery blueprint handler."""
from __future__ import annotations

from typing import Any, Mapping


def discover(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    notes = list((payload or {}).get("notes") or ["opportunity"])
    return {
        "pass": True,
        "opportunities": notes,
        "workflow_id": "wf.product-discovery",
    }
