#!/usr/bin/env python3
"""Documented Claude Code agent/command frontmatter contract, executable locally.

Source of the key lists and resolution rules: code.claude.com docs fetched
2026-08-24 (subagents + slash-commands/skills + tools-reference). This module
reproduces those rules for fixture subagents. It is not the Claude Code binary.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

# Documented agent YAML keys (subagents page, "Supported frontmatter fields").
# Only name and description are required on user/project/managed files.
AGENT_FRONTMATTER_KEYS: tuple[str, ...] = (
    "name",
    "description",
    "tools",
    "disallowedTools",
    "model",
    "permissionMode",
    "maxTurns",
    "skills",
    "mcpServers",
    "hooks",
    "memory",
    "background",
    "effort",
    "isolation",
    "color",
    "initialPrompt",
)

# Plugin-shipped agents: these three are ignored (docs: security).
PLUGIN_IGNORED_AGENT_KEYS: frozenset[str] = frozenset(
    {"hooks", "mcpServers", "permissionMode"}
)

# Documented command/skill YAML keys (slash-commands / skills frontmatter table).
COMMAND_FRONTMATTER_KEYS: tuple[str, ...] = (
    "name",
    "description",
    "when_to_use",
    "argument-hint",
    "arguments",
    "disable-model-invocation",
    "user-invocable",
    "allowed-tools",
    "disallowed-tools",
    "model",
    "effort",
    "context",
    "agent",
    "background",
    "hooks",
    "paths",
    "shell",
    "metadata",
    "license",
    "compatibility",
)

# Default spawn is a background subagent. Docs list this built-in pool.
BACKGROUND_SUBAGENT_TOOLS: frozenset[str] = frozenset(
    {
        "Read",
        "Grep",
        "Glob",
        "Bash",
        "PowerShell",
        "Edit",
        "Write",
        "NotebookEdit",
        "WebFetch",
        "WebSearch",
        "TodoWrite",
        "Skill",
        "ToolSearch",
        "EnterWorktree",
        "ExitWorktree",
        "Monitor",
        "TaskStop",
        "SendMessage",
        "Artifact",
    }
)

# First filter: never granted to a non-fork subagent even if listed in tools.
NEVER_GRANTED_TO_SUBAGENTS: frozenset[str] = frozenset(
    {
        "AskUserQuestion",
        "EndConversation",
        "EnterPlanMode",
        "ScheduleWakeup",
        "TaskOutput",
        "WaitForMcpServers",
        "Workflow",
    }
)

MODEL_ALIASES: frozenset[str] = frozenset(
    {"sonnet", "opus", "haiku", "fable", "inherit"}
)

FORBIDDEN_TOOL = "Bash"
FORBIDDEN_ARGV = "echo RES-0011-FORBIDDEN-CALL"
SAFE_BASH_RE = re.compile(r"^echo RES-0011-[A-Z0-9-]+$")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        raise ValueError("frontmatter-absent")
    rest = text[3:]
    end = rest.find("\n---")
    if end < 0:
        raise ValueError("frontmatter-unclosed")
    raw = rest[:end]
    body = rest[end + 4 :].lstrip("\n")
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter-not-mapping")
    return data, body


def parse_tool_names(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        parts = [str(v).strip() for v in value]
    else:
        parts = re.split(r"[\s,]+", str(value).strip())
    return [p for p in parts if p]


def _parent_pool() -> set[str]:
    return set(BACKGROUND_SUBAGENT_TOOLS) - set(NEVER_GRANTED_TO_SUBAGENTS)


def resolve_agent_tools(frontmatter: dict[str, Any]) -> dict[str, Any]:
    """Allowlist/denylist against the documented subagent pool.

    Docs (subagents + tools-reference, 2026-08-24): if both fields are set,
    disallowedTools is applied first, then tools is resolved against the
    remaining pool. A tool listed in both is removed. A name that is not in
    the subagent pool is never granted.
    """
    parent = _parent_pool()
    disallowed = set(parse_tool_names(frontmatter.get("disallowedTools")))
    remaining = parent - disallowed
    has_tools = "tools" in frontmatter and frontmatter.get("tools") not in (
        None,
        "",
        [],
    )
    if not has_tools:
        resolved = set(remaining)
        unresolved: list[str] = []
        mode = "inherit-minus-disallowed" if disallowed else "inherit"
    else:
        want = parse_tool_names(frontmatter.get("tools"))
        resolved = {t for t in want if t in remaining}
        unresolved = [t for t in want if t not in remaining]
        mode = "allowlist-against-remaining"
    if not resolved:
        return {
            "ok": False,
            "error": "zero-tools",
            "mode": mode,
            "tools": [],
            "unresolved": unresolved,
            "disallowed": sorted(disallowed),
            "restricts": True,
        }
    return {
        "ok": True,
        "error": None,
        "mode": mode,
        "tools": sorted(resolved),
        "unresolved": unresolved,
        "disallowed": sorted(disallowed),
        "restricts": True,
    }


def resolve_command_tools(frontmatter: dict[str, Any]) -> dict[str, Any]:
    """Command/skill tool fields.

    allowed-tools: pre-approval only. Docs: 'It does not restrict which tools
    are available: every tool remains callable.'
    disallowed-tools: removes from the available pool while the skill is active.
    """
    parent = set(BACKGROUND_SUBAGENT_TOOLS)
    preapproved = set(
        parse_tool_names(
            frontmatter.get("allowed-tools") or frontmatter.get("allowedTools")
        )
    )
    disallowed = set(
        parse_tool_names(
            frontmatter.get("disallowed-tools")
            or frontmatter.get("disallowedTools")
        )
    )
    available = parent - disallowed
    return {
        "ok": True,
        "available": sorted(available),
        "preapproved": sorted(preapproved),
        "disallowed": sorted(disallowed),
        "allowed_tools_restricts": False,
        "disallowed_tools_restricts": True,
        "restricts": bool(disallowed),
    }


def resolve_model(
    frontmatter: dict[str, Any],
    *,
    env_value: str | None = None,
    invocation_model: str | None = None,
    parent_model: str = "sonnet",
) -> dict[str, Any]:
    """Order from subagents docs: env, per-invocation, frontmatter, parent.

    env inherit (as of v2.1.196) is treated as unset.
    """
    env = env_value
    if env is None:
        env = os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL")
    if env == "inherit":
        env = None
    if env:
        return {"model": env, "source": "env", "parent_model": parent_model}
    inv = invocation_model
    if inv and inv != "inherit":
        return {
            "model": inv,
            "source": "invocation",
            "parent_model": parent_model,
        }
    fm = frontmatter.get("model") or "inherit"
    if fm and fm != "inherit":
        return {
            "model": str(fm),
            "source": "frontmatter",
            "parent_model": parent_model,
        }
    return {
        "model": parent_model,
        "source": "parent",
        "parent_model": parent_model,
    }


def load_definition(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    return {
        "path": str(path),
        "frontmatter": fm,
        "body": body,
        "keys_present": sorted(str(k) for k in fm.keys()),
    }


def agent_gate(path: Path) -> dict[str, Any]:
    loaded = load_definition(path)
    fm = loaded["frontmatter"]
    tools = resolve_agent_tools(fm)
    model = resolve_model(fm)
    return {**loaded, "kind": "agent", "tool_resolution": tools, "model": model}


def command_gate(path: Path) -> dict[str, Any]:
    loaded = load_definition(path)
    fm = loaded["frontmatter"]
    tools = resolve_command_tools(fm)
    model = resolve_model(fm)
    return {
        **loaded,
        "kind": "command",
        "tool_resolution": tools,
        "model": model,
    }


def attempt_agent_tool(gate: dict[str, Any], tool: str) -> dict[str, Any]:
    tr = gate["tool_resolution"]
    if not tr.get("ok"):
        return {
            "status": "REFUSED",
            "reason": tr.get("error") or "zero-tools",
            "tool": tool,
            "allowed_set": tr.get("tools") or [],
        }
    allowed = set(tr["tools"])
    if tool not in allowed:
        return {
            "status": "REFUSED",
            "reason": "not-in-resolved-tool-set",
            "tool": tool,
            "allowed_set": sorted(allowed),
        }
    return {
        "status": "ALLOWED",
        "reason": "in-resolved-tool-set",
        "tool": tool,
        "allowed_set": sorted(allowed),
    }


def attempt_command_tool(gate: dict[str, Any], tool: str) -> dict[str, Any]:
    tr = gate["tool_resolution"]
    available = set(tr["available"])
    if tool not in available:
        return {
            "status": "REFUSED",
            "reason": "command-disallowed-tools",
            "tool": tool,
            "available": sorted(available),
            "preapproved": tr["preapproved"],
        }
    return {
        "status": "ALLOWED",
        "reason": "command-pool-not-shrunk-by-allowed-tools",
        "tool": tool,
        "available": sorted(available),
        "preapproved": tr["preapproved"],
        "in_preapproved": tool in set(tr["preapproved"]),
    }
