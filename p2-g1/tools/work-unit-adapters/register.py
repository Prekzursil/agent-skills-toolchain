"""Work-unit adapter leak register (IMP-0422)."""
from __future__ import annotations

from typing import Any


class EmptyLeakRegister(RuntimeError):
    pass


class WorkUnitAdapter:
    adapter_id = "base"
    vendor = "none"
    source_path = "tools/work-unit-adapters/register.py"

    def classify_field(self, field: str, value: Any, unit: dict[str, Any]) -> dict[str, Any]:
        return {"status": "leaked", "reason": "unhandled", "consumed": False}

    def build_plan(self, unit: dict[str, Any]) -> dict[str, Any]:
        return {
            "prompt_transport": "file",
            "blocking": True,
            "detached_forbidden": True,
            "argv": ["adapter", "--prompt-file", "prompt.txt"],
        }

    def emit_leak_register(self, unit: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for field, value in unit.items():
            rec = self.classify_field(field, value, unit)
            rec["field"] = field
            rec["author"] = "adapter"
            rec["filled_by"] = "WorkUnitAdapter.emit_leak_register"
            rows.append(rec)
        leaked = [r for r in rows if r.get("status") in {"leaked", "partial"}]
        if not leaked:
            raise EmptyLeakRegister(self.adapter_id)
        return rows

    def dispatch(self, unit: dict[str, Any]) -> dict[str, Any]:
        register = self.emit_leak_register(unit)
        plan = self.build_plan(unit)
        return {
            "adapter_id": self.adapter_id,
            "vendor": self.vendor,
            "leak_register": register,
            "plan": plan,
        }


__all__ = ["EmptyLeakRegister", "WorkUnitAdapter"]
