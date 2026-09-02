#!/usr/bin/env python3
"""Host-owned contract adapter for BLD-0012.

Consumes recorded host payloads (Claude Code hook stdin, settings files,
plugin manifests, MCP initialize, slash-command frontmatter) and degrades
loudly. Silent accept of unknown events, extra fields, missing optionals,
or wrong-scope settings is a defect in this adapter.
"""
from __future__ import annotations

from typing import Any

HOOK_EVENTS = frozenset(
    {
        "SessionStart",
        "Setup",
        "UserPromptSubmit",
        "UserPromptExpansion",
        "PreToolUse",
        "PermissionRequest",
        "PermissionDenied",
        "PostToolUse",
        "PostToolUseFailure",
        "PostToolBatch",
        "Notification",
        "MessageDisplay",
        "SubagentStart",
        "SubagentStop",
        "TaskCreated",
        "TaskCompleted",
        "Stop",
        "StopFailure",
        "TeammateIdle",
        "InstructionsLoaded",
        "ConfigChange",
        "CwdChanged",
        "DirectoryAdded",
        "FileChanged",
        "WorktreeCreate",
        "WorktreeRemove",
        "PreCompact",
        "PostCompact",
        "Elicitation",
        "ElicitationResult",
        "SessionEnd",
    }
)

COMMON_REQUIRED = ("session_id", "cwd", "hook_event_name")
COMMON_OPTIONAL = (
    "prompt_id",
    "transcript_path",
    "permission_mode",
    "effort",
    "agent_id",
    "agent_type",
)
PRETOOL_REQUIRED = ("tool_name", "tool_input", "tool_use_id")
POSTTOOL_OPTIONAL = ("duration_ms",)

PLUGIN_KNOWN_FIELDS = frozenset(
    {
        "name",
        "displayName",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "metadata",
        "skills",
        "commands",
        "agents",
        "hooks",
        "mcpServers",
        "outputStyles",
        "lspServers",
        "experimental",
        "dependencies",
        "defaultEnabled",
    }
)
MCP_PROTOCOLS = frozenset(
    {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
)
SLASH_OPTIONAL = ("description", "argument-hint", "disable-model-invocation")


def _result(
    ok: bool, mode: str, code: str, message: str, extras: dict | None = None
) -> dict:
    out = {"ok": ok, "mode": mode, "code": code, "message": message}
    if extras:
        out.update(extras)
    return out


def _loud(code: str, message: str, mode: str = "DEGRADE") -> dict:
    if not message or not code:
        raise ValueError("loud degrade requires a named code and message")
    return _result(False, mode, code, message)


def parse_hook(payload: Any) -> dict:
    """Strict-parse a recorded hook stdin payload."""
    if not isinstance(payload, dict):
        return _loud("HOOK_NOT_OBJECT", "hook payload is not a JSON object", "REJECT")
    event = payload.get("hook_event_name")
    if not isinstance(event, str) or not event:
        return _loud("HOOK_EVENT_MISSING", "hook_event_name is required", "REJECT")
    if event not in HOOK_EVENTS:
        return _loud(
            "UNKNOWN_EVENT",
            f"unknown hook event name {event!r} is not a silent no-op",
            "REJECT",
        )
    missing_req = [k for k in COMMON_REQUIRED if k not in payload]
    if event in {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest"}:
        missing_req.extend(k for k in PRETOOL_REQUIRED if k not in payload)
    if missing_req:
        return _loud(
            "MISSING_REQUIRED",
            "missing required host fields: " + ",".join(missing_req),
            "REJECT",
        )
    allowed = set(COMMON_REQUIRED + COMMON_OPTIONAL + PRETOOL_REQUIRED + POSTTOOL_OPTIONAL)
    extra = sorted(k for k in payload if k not in allowed)
    if extra:
        return _loud(
            "UNKNOWN_FIELD",
            "unknown extra host field(s) " + ",".join(extra) + " must not be dropped silently",
        )
    # Version-gated optionals: missing is legal on the host, but this adapter
    # must not swallow the absence. prompt_id needs 2.1.196+; duration_ms
    # needs 2.1.119+ on PostToolUse*.
    gated: list[str] = []
    if event not in {"SessionStart", "Setup", "SessionEnd"} and "prompt_id" not in payload:
        gated.append("prompt_id")
    if event in {"PostToolUse", "PostToolUseFailure"} and "duration_ms" not in payload:
        gated.append("duration_ms")
    if gated:
        return _loud(
            "MISSING_OPTIONAL",
            "missing optional host field(s) "
            + ",".join(gated)
            + " — adapter degrades loudly rather than assuming defaults",
        )
    return _result(True, "ACCEPT", "OK", f"accepted {event} recorded payload")


def silent_unknown_event(payload: Any) -> dict:
    """Known-broken control: swallow unknown events. Must NOT be the shipped path."""
    return _result(True, "ACCEPT", "OK", "")


def check_settings_scope(doc: Any, file_kind: str) -> dict:
    """Detect wrong-scope / wrong-file writes of host settings keys.

    Estate-measured trap: disabledMcpServers at the root of ~/.claude.json is
    inert; the live map is projects[<path>].disabledMcpServers. Current docs
    also name deniedMcpServers / disabledMcpjsonServers in settings files.
    """
    if not isinstance(doc, dict):
        return _loud("SETTINGS_NOT_OBJECT", "settings document is not an object", "REJECT")
    findings: list[str] = []
    if file_kind == "claude.json":
        if "disabledMcpServers" in doc:
            findings.append(
                "WRONG_SCOPE:disabledMcpServers at ~/.claude.json root is inert; "
                "live path is projects[<abs-path>].disabledMcpServers "
                "(catalog trap + GitHub #44845)"
            )
        if "enabledPlugins" in doc:
            findings.append(
                "WRONG_FILE:enabledPlugins belongs in ~/.claude/settings.json, "
                "not ~/.claude.json"
            )
    elif file_kind == "settings.json":
        if "mcpServers" in doc:
            findings.append(
                "WRONG_FILE:mcpServers is read from ~/.claude.json or .mcp.json, "
                "not settings.json (silently ignored there)"
            )
        if "disabledMcpServers" in doc:
            findings.append(
                "WRONG_FILE:disabledMcpServers is not a settings.json key; "
                "current analogs are deniedMcpServers / disabledMcpjsonServers; "
                "the live disable map for /mcp is per-project in ~/.claude.json"
            )
        if "pluginConfigs" in doc and file_kind == "settings.json":
            # Project settings.json pluginConfigs stopped being read in 2.1.207.
            findings.append(
                "WRONG_SCOPE:pluginConfigs in project settings.json are ignored "
                "since Claude Code 2.1.207"
            )
    else:
        return _loud("UNKNOWN_FILE_KIND", f"unknown file_kind {file_kind!r}", "REJECT")

    if findings:
        return _loud("WRONG_SCOPE", "; ".join(findings), "REJECT")
    return _result(True, "ACCEPT", "OK", f"{file_kind} placement accepted")


def parse_plugin_manifest(doc: Any) -> dict:
    if not isinstance(doc, dict):
        return _loud("PLUGIN_NOT_OBJECT", "plugin.json is not an object", "REJECT")
    if "name" not in doc or not isinstance(doc.get("name"), str) or not doc["name"]:
        return _loud("PLUGIN_NAME_REQUIRED", "plugin.json name is required when a manifest exists", "REJECT")
    extra = sorted(k for k in doc if k not in PLUGIN_KNOWN_FIELDS)
    if extra:
        return _loud(
            "UNKNOWN_FIELD",
            "unknown plugin.json field(s) "
            + ",".join(extra)
            + " — host docs say unrecognized fields are ignored; this adapter degrades loudly",
        )
    if "version" not in doc:
        return _loud(
            "MISSING_OPTIONAL",
            "missing optional plugin.json field version — degrade loudly, do not assume latest",
        )
    return _result(True, "ACCEPT", "OK", "accepted plugin manifest")


def parse_mcp_initialize(doc: Any) -> dict:
    if not isinstance(doc, dict):
        return _loud("MCP_NOT_OBJECT", "MCP initialize is not an object", "REJECT")
    method = doc.get("method")
    if method != "initialize":
        return _loud("UNKNOWN_EVENT", f"unknown MCP method {method!r} is not a silent no-op", "REJECT")
    params = doc.get("params")
    if not isinstance(params, dict):
        return _loud("MISSING_REQUIRED", "MCP initialize params object is required", "REJECT")
    proto = params.get("protocolVersion")
    if not isinstance(proto, str):
        return _loud("MISSING_REQUIRED", "MCP protocolVersion is required", "REJECT")
    if proto not in MCP_PROTOCOLS:
        return _loud(
            "UNKNOWN_PROTOCOL",
            f"unknown MCP protocolVersion {proto!r}",
            "REJECT",
        )
    extra = sorted(k for k in params if k not in {"protocolVersion", "capabilities", "clientInfo"})
    if extra:
        return _loud("UNKNOWN_FIELD", "unknown MCP initialize field(s) " + ",".join(extra))
    if "capabilities" not in params:
        return _loud(
            "MISSING_OPTIONAL",
            "missing optional MCP initialize field capabilities — degrade loudly",
        )
    return _result(True, "ACCEPT", "OK", f"accepted MCP protocolVersion {proto}")


def parse_slash_frontmatter(doc: Any) -> dict:
    if not isinstance(doc, dict):
        return _loud("SLASH_NOT_OBJECT", "slash-command frontmatter is not an object", "REJECT")
    if "name" not in doc or not isinstance(doc.get("name"), str) or not doc["name"]:
        return _loud("MISSING_REQUIRED", "slash-command name is required", "REJECT")
    extra = sorted(
        k
        for k in doc
        if k not in {"name", "description", "argument-hint", "disable-model-invocation", "allowed-tools"}
    )
    if extra:
        return _loud("UNKNOWN_FIELD", "unknown slash-command frontmatter field(s) " + ",".join(extra))
    missing_opt = [k for k in SLASH_OPTIONAL if k not in doc]
    if missing_opt:
        return _loud(
            "MISSING_OPTIONAL",
            "missing optional slash-command field(s) " + ",".join(missing_opt),
        )
    return _result(True, "ACCEPT", "OK", "accepted slash-command frontmatter")
