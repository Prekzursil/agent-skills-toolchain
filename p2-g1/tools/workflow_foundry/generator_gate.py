"""Generator must consult before emit; ADOPT blocks rebuild (IMP-0211)."""
from __future__ import annotations

from typing import Any

from workflow_foundry.anti_rebuild_guard import ADOPT, BUILD, Registry, consult


class ConsultRequired(RuntimeError):
    pass


class RebuildBlocked(RuntimeError):
    def __init__(self, message: str, verdict: dict[str, Any] | None = None):
        super().__init__(message)
        self.verdict = verdict or {}


class GeneratorSession:
    def __init__(self, registry: Registry):
        self.registry = registry
        self._consulted: dict[str, Any] | None = None

    def consult(self, goal: dict[str, Any]) -> dict[str, Any]:
        result = consult(goal, self.registry).as_dict()
        self._consulted = result
        return result

    consult_goal = consult

    def emit(self, goal: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._consulted is None:
            raise ConsultRequired("consult before emit")
        action = (self._consulted or {}).get("action")
        if action == ADOPT:
            raise RebuildBlocked("incumbent blocks BUILD", verdict=self._consulted)
        if action != BUILD:
            raise ConsultRequired(f"unexpected action {action}")
        return {"emitted": True, "action": BUILD}

    def adopt_or_emit(self, goal: dict[str, Any], blueprint: dict[str, Any] | None = None) -> dict[str, Any]:
        guard = self.consult(goal)
        if guard.get("action") == ADOPT:
            return {"emitted": False, "guard": guard, "blueprint": blueprint}
        out = self.emit(goal)
        out["guard"] = guard
        out["blueprint"] = blueprint
        return out
