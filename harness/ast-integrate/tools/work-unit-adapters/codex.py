"""Codex work-unit adapter (IMP-0422)."""
from __future__ import annotations

from typing import Any

from register import WorkUnitAdapter

HONORED = frozenset({"timeout_seconds"})


class CodexAdapter(WorkUnitAdapter):
    adapter_id = "codex"
    vendor = "openai"
    source_path = "tools/work-unit-adapters/codex.py"

    def __init__(self, repo: Any = None, *args: Any, **kwargs: Any) -> None:
        self.repo = repo

    def classify_field(self, field: str, value: Any, unit: dict[str, Any]) -> dict[str, Any]:
        if field in HONORED:
            return {"status": "honored", "reason": "codex-consumed", "consumed": True}
        return {"status": "leaked", "reason": "codex-unconsumed", "consumed": False}

    def build_plan(self, unit: dict[str, Any]) -> dict[str, Any]:
        timeout = unit.get("timeout_seconds") or 120
        uid = str(unit.get("id") or "")
        prompt_file = f"command-center/p2-wave/probes/ARC-0042/fixtures/prompts/{uid}.md"
        return {
            "prompt_transport": "file",
            "blocking": True,
            "detached_forbidden": True,
            "prompt_file": prompt_file,
            "argv": [
                "codex",
                "exec",
                "--ignore-user-config",
                "--prompt-file",
                prompt_file,
                "--timeout",
                str(timeout),
            ],
            "ignore_user_config": True,
            "timeout_seconds": timeout,
        }


__all__ = ["CodexAdapter"]
