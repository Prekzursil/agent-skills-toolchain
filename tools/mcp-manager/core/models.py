"""Domain models for mcp-manager.

ServerRow   — one server (merged across planes); the unit the UI/CLI displays.
Loadout     — a named set of servers that should be disabled by default.
AuthStatus  — how the server authenticates (informational; from discovery).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AuthStatus(str, Enum):
    CONNECTED = "connected"
    NEEDS_AUTH = "needs_auth"
    FAILED = "failed"
    UNKNOWN = "unknown"

    @classmethod
    def from_glyph(cls, glyph: str) -> "AuthStatus":
        """Map the glyphs printed by 'claude mcp list' to an AuthStatus."""
        g = glyph.strip()
        if g in ("✔",):
            return cls.CONNECTED
        if g in ("!", "⚠"):
            return cls.NEEDS_AUTH
        if g in ("✘", "✗", "x"):
            return cls.FAILED
        return cls.UNKNOWN


@dataclass
class ServerRow:
    """Merged view of a single MCP server across all planes."""

    id: str                         # exact namespaced toggle identifier for Claude
    name: str                       # human-readable short name
    planes: list[str] = field(default_factory=list)
    enabled: bool = True
    status: AuthStatus = AuthStatus.UNKNOWN
    auth: str = ""                  # raw auth description from mcp list output
    command: str = ""               # transport/command string (informational)
    extra: dict[str, Any] = field(default_factory=dict)  # plane-specific raw data

    @property
    def duplicated(self) -> bool:
        return len(set(self.planes)) > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "planes": list(self.planes),
            "enabled": self.enabled,
            "status": self.status.value,
            "auth": self.auth,
            "command": self.command,
            "duplicated": self.duplicated,
        }


@dataclass
class Loadout:
    """A named set of server IDs that should be disabled by default.

    Backed by ~/.claude/.mcp-disabled-defaults.json.  The file shape is:
        {"disabledMcpServers": ["id1", "id2", ...], "_comment": "..."}

    The key 'disabledMcpServers' mirrors the per-project key in ~/.claude.json
    so the same IDs work across both files.
    """

    name: str = "defaults"
    disabled_ids: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)   # all keys from the file

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "disabled_ids": list(self.disabled_ids),
        }
