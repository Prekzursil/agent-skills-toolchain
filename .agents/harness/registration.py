from __future__ import annotations

from pathlib import Path
from typing import Any


# Native lifecycle events registered on both providers. The Agent-Teams and
# failure-channel names (TaskCreated/TaskCompleted/TeammateIdle,
# PostToolUseFailure/PermissionDenied), the config-drift name (ConfigChange) and
# the instruction-activation name (InstructionsLoaded, whose LedgerModule handler
# — modules.py `_append_instructions` — was reachable ONLY from a direct unit
# call until it was registered here, so its RULES activation telemetry could
# never actually be emitted in production)
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
    "InstructionsLoaded",
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
    "TeammateIdle",
    "Stop",
)

# 2026-10-13 lockstep raise with the live ~/.claude/settings.json UserPromptSubmit
# raise (dispatcher 25s there) and above the RAM-starvation floor: the old 2s/5s
# host deadlines fed dispatcher._dispatch_budget_sec (deadline - startup allowance),
# clamping module budgets to ~1.4s and letting every hot event die before its
# modules ran on the RAM-starved box. Hot events 25; SessionStart/Stop 60;
# PreCompact 30; the remaining events scaled x3 from their previous values.
# NOTE settings.json dispatcher entries for the other events still carry the OLD
# values until regenerated or hand-raised — _TIMEOUTS is meant to become the
# single source (structural fix is a tracked follow-up).
_TIMEOUTS = {
    "SessionStart": 35,
    "UserPromptSubmit": 25,
    "PreToolUse": 10,
    "PermissionRequest": 2,
    "PermissionDenied": 2,
    "PostToolUse": 10,
    "PostToolUseFailure": 2,
    "PreCompact": 5,
    "PostCompact": 3,
    "ConfigChange": 3,
    "InstructionsLoaded": 9,
    "SubagentStart": 3,
    "SubagentStop": 3,
    "TaskCreated": 3,
    "TaskCompleted": 5,
    "TeammateIdle": 3,
    "Stop": 35,
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
# `Agent` is the CURRENT name of the subagent-spawn tool; `Task` is its legacy name and is
# kept for older hosts. The rename was never followed here, so every subagent spawn missed
# the dispatcher entirely -- no goal re-anchor, no file-scope check, no lifecycle guard, no
# ledger record -- while a subagent can do anything a session can. Verified 2026-07-26
# against the live matcher: "Agent" did not match, "Task" did.
# Deliberately NOT widened to ".*": read-only tools (Read/Grep/Glob) need no gate, and
# gating them would cost a dispatcher run per call for no security gain.
_CLAUDE_PRETOOLUSE_MATCHER = "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit|apply_patch|Agent|Task|WebFetch|mcp__.*"


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
    # `grok` accepted so this gate agrees with adapters.SUPPORTED_PROVIDERS (live
    # tree 2026-08-08, ported 2026-09-02). NOTE the two sets govern DIFFERENT axes
    # and are not required to stay equal forever: SUPPORTED_PROVIDERS is the
    # RUNTIME set (whose events we process), this is the GENERATION set (whose
    # config we can emit). install.py writes only the claude and codex documents;
    # Grok's hook file is `~/.grok/hooks/imported-from-claude.json`, produced by
    # Grok's OWN importer, not by this function. So nothing calls
    # build_hooks("grok") today — this is a consistency fix for a LATENT trap, not
    # a live install path. Do not infer that the harness installs Grok's config.
    if provider_name not in {"claude", "codex", "grok"}:
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
            #
            # grok DELIBERATELY keeps ".*" — a measured decision, not an accidental
            # inheritance of the codex path. _CLAUDE_PRETOOLUSE_MATCHER enumerates
            # CLAUDE tool names, and Grok's tool names are different. Measured
            # 2026-08-08 against the shipped grok.exe: the Claude matcher matches
            # 1 of 13 real Grok tool names (`Agent`) and MISSES run_terminal_command,
            # search_replace, write_file, create_file, delete_file, read_file,
            # list_dir, grep, glob, web_search, web_fetch, todo_write. Narrowing
            # grok would make the destructive-command guard blind to every Grok
            # shell command and every Grok file write. If grok is ever narrowed, it
            # needs its OWN matcher built from Grok tool names, never this constant.
            if provider_name == "claude" and event_name == "PreToolUse":
                group["matcher"] = _CLAUDE_PRETOOLUSE_MATCHER
            else:
                group["matcher"] = ".*"
        result[event_name] = [group]
    # Claude alone carries the live settings.json hand-edits; codex output is
    # unchanged (byte-identical to the pre-fix block).
    #
    # grok gets NONE of them, deliberately. Two of the four hand-edits register
    # WorktreeCreate / WorktreeRemove, and Grok's hook-event list (measured
    # 2026-08-08 from grok.exe: SessionStart, UserPromptSubmit, PreToolUse,
    # PostToolUse, PostToolUseFailure, PermissionDenied, Stop, StopFailure,
    # Notification, SubagentStart, SubagentStop, PreCompact, PostCompact,
    # SessionEnd) contains neither — Grok would log "ignoring unknown event".
    # The other two point into ~/.claude/hooks/ at Claude-only tooling.
    if provider_name == "claude":
        _apply_claude_hand_edits(result)
    return result
