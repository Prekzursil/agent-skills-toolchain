"""Old MCP-thread rail: CodexAdapter.build_plan + last-message artifact.

Does not spawn a live Codex binary (tools/work-unit-adapters/codex.py).
mcp_thread_id is vendor-only remainder; portable payload is the last-message body.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ADAPTERS = REPO / "tools" / "work-unit-adapters"
# Prefer a delivered work-unit adapter; otherwise WRAP via the local
# agentspec.argv builder in this probe directory.
sys.path.insert(0, str(HERE))
if (ADAPTERS / "codex.py").is_file():
    sys.path.insert(0, str(ADAPTERS))

from codex import CodexAdapter  # noqa: E402


def old_artifact(unit: Mapping[str, Any], repo: Path) -> dict[str, Any]:
    uid = str(unit.get("id") or "")
    sentinel = str(unit.get("completion_sentinel") or "")
    adapter = CodexAdapter(repo)
    plan = adapter.build_plan(unit)
    if not plan.get("blocking") or plan.get("prompt_transport") != "file":
        raise RuntimeError(f"{uid}: Codex plan is not blocking prompt-by-file")
    if any(tok in {"&", "--background", "--detach"} for tok in plan.get("argv") or []):
        raise RuntimeError(f"{uid}: detached token on Codex argv")
    body = {
        "unit_id": uid,
        "sentinel": sentinel,
        "output_path": unit.get("output_path"),
        "prompt_file": plan["prompt_file"],
        "argv": list(plan["argv"]),
        "blocking": True,
        "prompt_transport": "file",
        "ignore_user_config": bool(plan.get("ignore_user_config")),
        "timeout_seconds": plan.get("timeout_seconds"),
    }
    return {
        "unit_id": uid,
        "sentinel": sentinel,
        "body": body,
        "mcp_thread_id": f"thr-{uid}",
        "mcp_tool": "mcp__codex__codex",
        "mcp_reply_tool": "mcp__codex__codex-reply",
    }
