#!/usr/bin/env python3
"""Live estate census, registered hooks, and both-states payloads for TST-0086."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HOOKS = REPO / "hooks"
DISPATCH_PY = HOOKS / "_dispatch" / "dispatch.py"
DISPATCH_MANIFEST = HOOKS / "_dispatch" / "manifest.json"
SETTINGS = REPO / "agent-self" / "config" / "settings.json"
HOOKS_MD = REPO / "rules" / "common" / "hooks.md"
NO_FORCE_PUSH = HOOKS / "no-force-push" / "hook.py"

WIN_HOOK = re.compile(
    r'C:/Users/Prekzursil/\.claude/hooks/([^"\s]+)', re.IGNORECASE
)
WIN_AGENTS = re.compile(
    r'C:/Users/Prekzursil/\.agents/([^"\s]+)', re.IGNORECASE
)

ESTATE_INPUTS = (
    "hooks/_dispatch/dispatch.py",
    "hooks/_dispatch/manifest.json",
    "rules/common/hooks.md",
    "agent-self/config/settings.json",
    "hooks/no-force-push/hook.py",
)

SAFE_BASH = {
    "hook_event_name": "PreToolUse",
    "tool_name": "Bash",
    "tool_input": {"command": "ls -la"},
    "session_id": "tst-0086-safe",
}

ADVISORY_BASH = {
    "hook_event_name": "PreToolUse",
    "tool_name": "Bash",
    "tool_input": {"command": "git log --oneline -1"},
    "session_id": "tst-0086-advisory",
}

DANGER_BASH = {
    "hook_event_name": "PreToolUse",
    "tool_name": "Bash",
    "tool_input": {"command": "git push --force origin main"},
    "session_id": "tst-0086-danger",
}

SESSION_START = {
    "hook_event_name": "SessionStart",
    "source": "startup",
    "session_id": "tst-0086-session",
}

DISPATCH_EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "Stop")
EVENT_CLI = {
    "SessionStart": "sessionstart",
    "PreToolUse": "pretooluse",
    "PostToolUse": "posttooluse",
    "Stop": "stop",
}


def extra_argv(command: str, rel: str) -> list[str]:
    """Best-effort argv after the quoted Windows hook path."""
    low = command.replace("\\", "/")
    needle = rel.replace("\\", "/")
    idx = low.lower().find(needle.lower())
    if idx < 0:
        return []
    rest = command[idx + len(needle) :]
    rest = rest.replace('"', " ").strip()
    if not rest:
        return []
    return rest.split()


def settings_hook_rows() -> list[dict[str, Any]]:
    doc = json.loads(SETTINGS.read_text(encoding="utf-8"))
    hooks_cfg = doc.get("hooks") or {}
    rows: list[dict[str, Any]] = []

    def walk(obj: Any, event: str | None, matcher: str | None) -> None:
        if isinstance(obj, dict):
            if isinstance(obj.get("command"), str) and obj.get("type") == "command":
                rows.append(
                    {
                        "event": event,
                        "matcher": matcher,
                        "command": obj["command"],
                    }
                )
            for val in obj.values():
                walk(val, event, matcher)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, event, matcher)

    if isinstance(hooks_cfg, dict):
        for event, entries in hooks_cfg.items():
            if not isinstance(entries, list):
                continue
            for group in entries:
                matcher = None
                if isinstance(group, dict):
                    matcher = group.get("matcher")
                walk(group, str(event), matcher)
    return rows


def classify_command(command: str) -> dict[str, Any]:
    hook = WIN_HOOK.search(command)
    if hook:
        rel = hook.group(1).replace("\\", "/")
        path = HOOKS / rel
        return {
            "kind": "settings-hook",
            "rel": f"hooks/{rel}",
            "path": path,
            "exists": path.is_file(),
            "suffix": path.suffix.lower(),
            "argv": extra_argv(command, rel),
        }
    agents = WIN_AGENTS.search(command)
    if agents:
        rel = agents.group(1).replace("\\", "/")
        return {
            "kind": "harness-dispatcher",
            "rel": f".agents/{rel}",
            "path": None,
            "exists": False,
            "suffix": "",
            "argv": [],
        }
    return {
        "kind": "other",
        "rel": command,
        "path": None,
        "exists": False,
        "suffix": "",
        "argv": [],
    }


def unique_settings_python_hooks() -> list[dict[str, Any]]:
    """One row per on-disk Python hook registered in agent-self/config/settings.json."""
    found: dict[str, dict[str, Any]] = {}
    for raw in settings_hook_rows():
        classified = classify_command(str(raw["command"]))
        if classified["kind"] != "settings-hook":
            continue
        if classified["suffix"] != ".py" or not classified["exists"]:
            continue
        rel = str(classified["rel"])
        hid = f"hook.settings:{rel}"
        if hid in found:
            continue
        found[hid] = {
            "id": hid,
            "kind": "settings",
            "event": raw.get("event"),
            "matcher": raw.get("matcher"),
            "rel": rel,
            "path": classified["path"],
            "argv": classified["argv"],
            "command": raw.get("command"),
        }
    return list(found.values())


def dispatch_event_hooks() -> list[dict[str, Any]]:
    return [
        {
            "id": f"hook.dispatch:{event}",
            "kind": "dispatch-event",
            "event": event,
            "cli": EVENT_CLI[event],
            "rel": "hooks/_dispatch/dispatch.py",
            "path": DISPATCH_PY,
            "argv": [EVENT_CLI[event]],
        }
        for event in DISPATCH_EVENTS
    ]


def registered_hooks() -> list[dict[str, Any]]:
    """Fail-open targets: each unique live settings Python hook + each dispatch event."""
    return unique_settings_python_hooks() + dispatch_event_hooks()


def dispatch_check_census() -> list[dict[str, Any]]:
    man = json.loads(DISPATCH_MANIFEST.read_text(encoding="utf-8"))
    rows = []
    for event, body in (man.get("events") or {}).items():
        if not isinstance(body, dict):
            continue
        for chk in body.get("checks") or []:
            if not isinstance(chk, dict):
                continue
            script = str(chk.get("script") or "").replace("\\", "/")
            path = HOOKS / script
            rows.append(
                {
                    "event": event,
                    "name": chk.get("name"),
                    "script": script,
                    "exists": path.is_file(),
                    "timeout": chk.get("timeout"),
                    "matcher": chk.get("matcher"),
                }
            )
    return rows


def skipped_registrations() -> list[dict[str, Any]]:
    skipped = []
    seen_rel = set()
    for raw in settings_hook_rows():
        classified = classify_command(str(raw["command"]))
        rel = str(classified.get("rel") or "")
        key = (classified["kind"], rel)
        if key in seen_rel:
            continue
        seen_rel.add(key)
        if classified["kind"] == "settings-hook" and classified["suffix"] == ".py":
            continue
        skipped.append(
            {
                "kind": classified["kind"],
                "rel": rel,
                "suffix": classified.get("suffix"),
                "reason": (
                    "windows-ps1"
                    if classified.get("suffix") == ".ps1"
                    else classified["kind"]
                ),
                "event": raw.get("event"),
            }
        )
    return skipped


def estate_census() -> dict[str, Any]:
    rows = []
    for rel in ESTATE_INPUTS:
        path = REPO / rel
        rows.append(
            {
                "path": rel,
                "present": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    checks = dispatch_check_census()
    settings_py = unique_settings_python_hooks()
    skipped = skipped_registrations()
    present = all(r["present"] for r in rows)
    return {
        "repo_root": str(REPO),
        "estate_inputs_present": present,
        "rows": rows,
        "sut": "hooks/_dispatch/dispatch.py",
        "danger_sut": "hooks/no-force-push/hook.py",
        "settings_python_hook_count": len(settings_py),
        "dispatch_check_count": len(checks),
        "dispatch_checks_all_exist": all(c["exists"] for c in checks) and bool(checks),
        "skipped": skipped,
        "claim": (
            "Live SUT is hooks/_dispatch/dispatch.py (inject-only, always "
            "exit 0) plus standalone settings.json gates. Danger block is "
            "hooks/no-force-push/hook.py (exit 2 on git push --force). Not a "
            "claim that ~/.claude host wrap or ~/.agents/harness/dispatcher.py "
            "were executed on this Linux worktree."
        ),
    }
