from __future__ import annotations

from pathlib import Path
from typing import Any


EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PermissionRequest",
    "PermissionDenied",
    "PostToolUse",
    "PostToolUseFailure",
    "PreCompact",
    "PostCompact",
    "ConfigChange",
    "InstructionsLoaded",
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
    "TeammateIdle",
    "Stop",
)

_TIMEOUTS = {
    "SessionStart": 5,
    "UserPromptSubmit": 5,
    "PreToolUse": 5,
    "PermissionRequest": 5,
    "PermissionDenied": 5,
    "PostToolUse": 5,
    "PostToolUseFailure": 5,
    "PreCompact": 5,
    "PostCompact": 5,
    "ConfigChange": 5,
    "InstructionsLoaded": 5,
    "SubagentStart": 5,
    "SubagentStop": 5,
    "TaskCreated": 5,
    "TaskCompleted": 5,
    "TeammateIdle": 5,
    "Stop": 5,
}
_NO_MATCHER = {"UserPromptSubmit", "Stop"}

_CLAUDE_PRETOOLUSE_MATCHER = "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit|apply_patch|Agent|Task|WebFetch|mcp__.*"


def _command_group(
    command: str, *, timeout: int, status: str, matcher: str | None
) -> dict[str, Any]:
    group: dict[str, Any] = {
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": timeout,
                "statusMessage": status,
            }
        ]
    }
    if matcher is not None:
        group["matcher"] = matcher
    return group


def _apply_claude_hand_edits(result: dict[str, list[dict[str, Any]]]) -> None:
    hooks_root = (Path.home() / ".claude" / "hooks").as_posix()
    result["SessionStart"].append(
        _command_group(
            f'python "{hooks_root}/local-tui-reminder/check.py"',
            timeout=5,
            status="local-TUI reminder",
            matcher=".*",
        )
    )
    result["PreToolUse"].append(
        _command_group(
            f'python "{hooks_root}/workflow-monitor-autolaunch/check.py"',
            timeout=8,
            status="wfmon auto-launch",
            matcher="Workflow",
        )
    )
    result["WorktreeCreate"] = [
        _command_group(
            "powershell -NoProfile -ExecutionPolicy Bypass -File "
            f'"{hooks_root}/create-worktree.ps1"',
            timeout=60,
            status="Creating git worktree",
            matcher=None,
        )
    ]
    result["WorktreeRemove"] = [
        _command_group(
            "powershell -NoProfile -ExecutionPolicy Bypass -File "
            f'"{hooks_root}/remove-worktree.ps1"',
            timeout=30,
            status="Removing git worktree",
            matcher=None,
        )
    ]


def build_hooks(provider: str) -> dict[str, list[dict[str, Any]]]:
    provider_name = str(provider).lower()
    if provider_name not in {"claude", "codex", "grok"}:
        raise ValueError(f"unsupported provider: {provider_name}")
    dispatcher = (Path(__file__).resolve().parent / "dispatcher.py").as_posix()
    result: dict[str, list[dict[str, Any]]] = {}
    for event_name in EVENTS:
        command = f'python -X utf8 "{dispatcher}" --provider {provider_name} --event {event_name}'
        group: dict[str, Any] = {
            "hooks": [
                {
                    "type": "command",
                    "command": command,
                    "timeout": _TIMEOUTS[event_name],
                    "statusMessage": f"Shared harness: {event_name}",
                }
            ]
        }
        if event_name not in _NO_MATCHER:
            if provider_name == "claude" and event_name == "PreToolUse":
                group["matcher"] = _CLAUDE_PRETOOLUSE_MATCHER
            else:
                group["matcher"] = ".*"
        result[event_name] = [group]
    if provider_name == "claude":
        _apply_claude_hand_edits(result)
    return result
