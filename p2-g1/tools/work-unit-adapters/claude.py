"""Claude work-unit adapter (IMP-0422)."""
from __future__ import annotations

from typing import Any

from register import WorkUnitAdapter

HONORED = frozenset(
    {
        "timeout_seconds",
        "assigned_model_vendor_role",
        "execution_substrate",
    }
)


class ClaudeAdapter(WorkUnitAdapter):
    adapter_id = "claude"
    vendor = "anthropic"
    source_path = "tools/work-unit-adapters/claude.py"

    def classify_field(self, field: str, value: Any, unit: dict[str, Any]) -> dict[str, Any]:
        if field in HONORED:
            return {"status": "honored", "reason": "claude-consumed", "consumed": True}
        return {"status": "leaked", "reason": "claude-unconsumed", "consumed": False}

    def build_plan(self, unit: dict[str, Any]) -> dict[str, Any]:
        timeout = unit.get("timeout_seconds") or 120
        return {
            "prompt_transport": "file",
            "blocking": True,
            "detached_forbidden": True,
            "argv": ["claude", "--prompt-file", "prompt.txt", "--timeout", str(timeout)],
        }


__all__ = ["ClaudeAdapter"]
