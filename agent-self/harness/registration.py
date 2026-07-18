from __future__ import annotations

from pathlib import Path
from typing import Any


# Native lifecycle events registered on both providers. The Agent-Teams and
# failure-channel names (TaskCreated/TaskCompleted/TeammateIdle,
# PostToolUseFailure/PermissionDenied) and the config-drift name (ConfigChange)
# are POST-CUTOFF Claude Code features: they are registered fail-open (an
# unknown event name is simply never fired by a host that does not emit it) so
# the shared harness observes them the moment the host starts emitting them,
# with zero behaviour change on hosts that do not. Keeping every registered
# name here (plus a matching _TIMEOUTS entry) is what lets desired_documents()
# regenerate byte-identical hook blocks so `install.py --check` stays drift-free
# for the harness-owned registration surface.
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
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
    "TeammateIdle",
    "Stop",
)

_TIMEOUTS = {
    "SessionStart": 5,
    "UserPromptSubmit": 2,
    "PreToolUse": 2,
    "PermissionRequest": 2,
    "PermissionDenied": 2,
    "PostToolUse": 2,
    "PostToolUseFailure": 2,
    "PreCompact": 5,
    "PostCompact": 3,
    "ConfigChange": 3,
    "SubagentStart": 3,
    "SubagentStop": 3,
    "TaskCreated": 3,
    "TaskCompleted": 5,
    "TeammateIdle": 3,
    "Stop": 5,
}
_NO_MATCHER = {"UserPromptSubmit", "Stop"}

# --------------------------------------------------------------------------- #
# Claude-only hand-edits (folded in so a regenerated CLAUDE hooks block matches
# the live ~/.claude/settings.json).
#
# These five deltas exist ONLY in the live Claude settings and are NOT emitted
# for codex. Folding them into build_hooks("claude") is what keeps
# `install.py --check` drift-free for the harness-owned surface AND stops a bare
# `python install.py` from silently WIPING them when it regenerates the block:
#   (a) the PreToolUse dispatcher matcher is hand-narrowed to the gated tool set
#       (codex keeps the broad ".*");
#   (b) a 2nd SessionStart group runs the local-TUI reminder;
#   (c) a 2nd PreToolUse group (matcher "Workflow") auto-launches wfmon;
#   (d)/(e) WorktreeCreate/WorktreeRemove drive the PowerShell worktree scripts.
# Paths resolve from Path.home() so the generated block matches the live literal
# (C:/Users/<user>/...) without hard-coding a username.
# --------------------------------------------------------------------------- #
_CLAUDE_PRETOOLUSE_MATCHER = "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit|apply_patch|Task|WebFetch|mcp__.*"


def _command_group(
    command: str, *, timeout: int, status: str, matcher: str | None
) -> dict[str, Any]:
    """One hook group ({[matcher,] hooks:[{type,command,timeout,statusMessage}]}).

    Mirrors the dispatcher group shape build_hooks emits; ``matcher=None`` omits
    the key entirely (used for the no-matcher WorktreeCreate/WorktreeRemove
    groups, matching UserPromptSubmit/Stop)."""
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
    """Fold the four ADDED Claude-only groups into an already-built hook block.

    The PreToolUse matcher narrowing (edit a) is applied inline in build_hooks;
    this adds edits (b)-(e). Mutates ``result`` in place."""
    hooks_root = (Path.home() / ".claude" / "hooks").as_posix()
    # (b) 2nd SessionStart group: the local-TUI reminder.
    result["SessionStart"].append(
        _command_group(
            f'python "{hooks_root}/local-tui-reminder/check.py"',
            timeout=5,
            status="local-TUI reminder",
            matcher=".*",
        )
    )
    # (c) 2nd PreToolUse group: workflow-monitor auto-launch (matcher "Workflow").
    result["PreToolUse"].append(
        _command_group(
            f'python "{hooks_root}/workflow-monitor-autolaunch/check.py"',
            timeout=8,
            status="wfmon auto-launch",
            matcher="Workflow",
        )
    )
    # (d)/(e) WorktreeCreate + WorktreeRemove: the PowerShell worktree lifecycle
    # (no matcher — a lifecycle event, like UserPromptSubmit/Stop).
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
    if provider_name not in {"claude", "codex"}:
        raise ValueError(f"unsupported provider: {provider_name}")
    dispatcher = (Path(__file__).resolve().parent / "dispatcher.py").as_posix()
    result: dict[str, list[dict[str, Any]]] = {}
    for event_name in EVENTS:
        command = (
            f'python "{dispatcher}" --provider {provider_name} --event {event_name}'
        )
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
            # (a) Claude hand-narrows the PreToolUse dispatcher matcher to the
            # gated tool set; every other event (and all of codex) keeps ".*".
            if provider_name == "claude" and event_name == "PreToolUse":
                group["matcher"] = _CLAUDE_PRETOOLUSE_MATCHER
            else:
                group["matcher"] = ".*"
        result[event_name] = [group]
    # Claude alone carries the live settings.json hand-edits; codex output is
    # unchanged (byte-identical to the pre-fix block).
    if provider_name == "claude":
        _apply_claude_hand_edits(result)
    return result
