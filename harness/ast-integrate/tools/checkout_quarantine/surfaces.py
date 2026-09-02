"""Auto-load surfaces of a cloned checkout and the threat class each one carries.

A repository can ship agent configuration that a tool loads the moment the
checkout is opened: Claude settings and hooks, a Codex project config, an MCP
server manifest. Opening an untrusted clone must therefore never *execute* any of
these; TST-0216 quarantines them and records what was found.
"""
from __future__ import annotations

CVE_2026_47751_CLASS = "CVE-2026-47751-class"

# Surfaces in the order they are enumerated and quarantined.
EXPECTED = (".claude", ".codex", ".mcp.json", "hooks")

# What a naive agent would do with each surface when it auto-loads a checkout.
AUTOLOAD_ACTION = {
    ".claude": "read settings.json and register its hooks and permissions",
    ".codex": "trust the project config.toml (CVE-2026-47751 class: cloned-repo auto-load)",
    ".mcp.json": "start every MCP server the manifest names",
    "hooks": "run the hook scripts on the next tool event",
}

THREAT_CLASSES = {
    ".claude": "auto-load-agent-config",
    ".codex": CVE_2026_47751_CLASS,
    ".mcp.json": "auto-load-mcp-servers",
    "hooks": "auto-load-hook-scripts",
}


def threat_class_for(relpath: str) -> str:
    return THREAT_CLASSES.get(relpath, "auto-load-agent-config")


__all__ = [
    "AUTOLOAD_ACTION",
    "CVE_2026_47751_CLASS",
    "EXPECTED",
    "THREAT_CLASSES",
    "threat_class_for",
]
