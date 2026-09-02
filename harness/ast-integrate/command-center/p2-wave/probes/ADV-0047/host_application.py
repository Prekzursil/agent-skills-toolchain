#!/usr/bin/env python3
"""Launch the host application against ADV0047_PROFILE.

Reads leftover hooks, MCP registrations and scheduled tasks from the
profile and attempts to activate each. Prints one JSON object on stdout.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from common import HOOK_ID, PACKAGE_ID, TASK_ID

PROFILE = Path(os.environ.get("ADV0047_PROFILE") or "")
EFFECT = Path(os.environ.get("ADV0047_EFFECT_DIR") or "")


def _run(script: Path, extra_args: list[str] | None = None) -> dict:
    if not script.is_file():
        return {"ran": False, "reason": "script-missing", "path": str(script)}
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [sys.executable, "-B", str(script)]
    if extra_args:
        cmd.extend(extra_args)
    proc = subprocess.run(
        cmd, env=env, capture_output=True, text=True, timeout=15
    )
    return {
        "ran": True,
        "exit_code": proc.returncode,
        "path": str(script),
        "pid_parent": os.getpid(),
    }


def main() -> int:
    if not PROFILE.is_dir():
        print(json.dumps({"ok": False, "error": "profile-missing"}))
        return 2
    harness = PROFILE / "AppData" / "Roaming" / "harness"
    plugin = harness / "plugins" / PACKAGE_ID
    hooks_dispatch = plugin / "hooks.json"
    hook_activated = False
    hook_detail: dict = {"loaded": False, "fired": False}
    if hooks_dispatch.is_file():
        try:
            dispatch = json.loads(hooks_dispatch.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            dispatch = {}
        for item in dispatch.get("hooks") or []:
            if not isinstance(item, dict):
                continue
            if item.get("id") != HOOK_ID:
                continue
            script = plugin / str(item.get("script") or "")
            hook_detail = _run(script)
            marker = EFFECT / "hook.json"
            hook_activated = marker.is_file() and hook_detail.get("ran") is True
            hook_detail["loaded"] = True
            hook_detail["fired"] = hook_activated
    mcp_path = PROFILE / "AppData" / "Roaming" / "mcp" / "mcp.json"
    mcp_activated = False
    mcp_detail: dict = {"registered": False, "fired": False}
    if mcp_path.is_file():
        try:
            mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            mcp = {}
        servers = mcp.get("mcpServers") or {}
        if PACKAGE_ID in servers:
            mcp_detail["registered"] = True
            spec = servers[PACKAGE_ID]
            command = Path(str(spec.get("command") or ""))
            args = [str(a) for a in (spec.get("args") or [])]
            mcp_detail.update(_run(command, args))
            mcp_activated = (EFFECT / "mcp.json").is_file()
            mcp_detail["fired"] = mcp_activated
    task_path = harness / "tasks" / f"{TASK_ID}.json"
    task_activated = False
    task_detail: dict = {"registered": False, "fired": False}
    if task_path.is_file():
        try:
            task = json.loads(task_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            task = {}
        if task.get("enabled") and task.get("id") == TASK_ID:
            task_detail["registered"] = True
            command = Path(str(task.get("command") or ""))
            args = [str(a) for a in (task.get("args") or [])]
            task_detail.update(_run(command, args))
            task_activated = (EFFECT / "task.json").is_file()
            task_detail["fired"] = task_activated
    out = {
        "ok": True,
        "host_pid": os.getpid(),
        "plugin_dir_present": plugin.is_dir(),
        "hook": {
            "id": HOOK_ID,
            "activated": hook_activated,
            **hook_detail,
        },
        "mcp": {
            "id": PACKAGE_ID,
            "activated": mcp_activated,
            **mcp_detail,
        },
        "task": {
            "id": TASK_ID,
            "activated": task_activated,
            **task_detail,
        },
        "any_package_activation": bool(hook_activated or mcp_activated or task_activated),
    }
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
