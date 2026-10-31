"""Compile a CouncilSpec that always hands off to phase-7A."""
from __future__ import annotations

import hashlib
from typing import Any

from blueprint_library.inventory import DELEGATED_IDS


def compile_council_spec(protocol_id: str, ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = ctx or {}
    return {
        "protocol_id": protocol_id,
        "deliberation_implemented_here": False,
        "delegate_to": {"runtime": "phase-7A", "seed": ctx.get("seed")},
        "kind": "CouncilSpec",
    }


def delegated_fingerprints() -> dict[str, str]:
    out: dict[str, str] = {}
    for protocol_id in DELEGATED_IDS:
        raw = f"delegated:{protocol_id}".encode("utf-8")
        out[protocol_id] = hashlib.sha256(raw).hexdigest()
    return out
