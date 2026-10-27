"""Hand a compiled CouncilSpec to the phase-7A runtime."""
from __future__ import annotations

from typing import Any


def delegate_to_phase7a(spec: dict[str, Any]) -> dict[str, Any]:
    runtime = (spec.get("delegate_to") or {}).get("runtime")
    return {
        "kind": "phase7a-handoff",
        "spec_protocol_id": spec.get("protocol_id"),
        "runtime_present": runtime == "phase-7A",
        "status": "handed-off",
        "runtime": runtime,
    }
