#!/usr/bin/env python3
"""Fixture estate encoding B02 measured curation facts (not the absent Windows live tree).

Surfaces:
  home/.mcp.json                         declared MCP servers
  home/.claude.json                      root + per-project blocks
  home/.claude/settings.json             enabledPlugins (not ~/.claude.json)
  live/processes.json                    spawned MCP processes
  live/tools.json                        reachable tools / plugin skills

Encoded traps (AUD-0015 / AUD-0016):
  * root disabledMcpServers is INERT
  * per-project disabledMcpServers is the effective disable
  * enabledPlugins lives in settings.json
  * plugin agentbridge is known-disabled and must remain so
  * MCP memory is declared but not spawned (exposed-versus-active split)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT = "/opt/p2/ast-integrate"
KNOWN_DISABLED_PLUGIN = "agentbridge"
KNOWN_DISABLED_MCP = "agentbridge"
EXPOSED_INACTIVE_MCP = "memory"
ROOT_INERT_DISABLE = "filesystem"

MCP_JSON = {
    "mcpServers": {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        },
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
        },
        "memory": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
        },
    }
}

CLAUDE_JSON = {
    "disabledMcpServers": {ROOT_INERT_DISABLE: True},
    "projects": {
        PROJECT: {
            "mcpServers": {
                KNOWN_DISABLED_MCP: {
                    "command": "node",
                    "args": ["agentbridge-mcp.js"],
                }
            },
            "disabledMcpServers": {KNOWN_DISABLED_MCP: True},
        }
    },
}

SETTINGS_JSON = {
    "enabledPlugins": {
        "harness": True,
        KNOWN_DISABLED_PLUGIN: False,
        "council": True,
    }
}

PROCESSES = {
    "processes": [
        {"name": "filesystem", "pid": 1101, "cmd": "mcp-filesystem"},
        {"name": "github", "pid": 1102, "cmd": "mcp-github"},
    ]
}

TOOLS = {
    "tools": [
        {"server": "filesystem", "names": ["read_file", "write_file"]},
        {"server": "github", "names": ["get_file", "list_issues"]},
    ],
    "plugin_skills_reachable": ["harness", "council"],
}


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def write_estate(root: Path) -> dict[str, str]:
    """Write the fixture estate. Returns relative path -> file text."""
    files = {
        "home/.mcp.json": dumps(MCP_JSON),
        "home/.claude.json": dumps(CLAUDE_JSON),
        "home/.claude/settings.json": dumps(SETTINGS_JSON),
        "live/processes.json": dumps(PROCESSES),
        "live/tools.json": dumps(TOOLS),
    }
    for rel, text in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8", newline="\n")
    (root / "gateway").mkdir(parents=True, exist_ok=True)
    (root / "freeze").mkdir(parents=True, exist_ok=True)
    return files
