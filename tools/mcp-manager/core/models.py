"""Domain models for mcp-manager.

ServerRow   — one server (merged across planes); the unit the UI/CLI displays.
Loadout     — a named set of servers that should be disabled by default.
AuthStatus  — how the server authenticates (informational; from discovery).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AuthStatus(str, Enum):
    CONNECTED = "connected"
    NEEDS_AUTH = "needs_auth"
    FAILED = "failed"
    # Deliberately switched off by curation (disabledMcpServers) — an intentional
    # state, NOT a health failure.  Never derived from a handshake glyph.
    DISABLED = "disabled"
    UNKNOWN = "unknown"

    @classmethod
    def from_glyph(cls, glyph: str) -> "AuthStatus":
        """Map the glyphs printed by 'claude mcp list' to an AuthStatus.

        'claude mcp list' reports handshake health only; it has no disabled
        glyph, so DISABLED is never produced here — it is applied by
        claude_adapter.reconcile_enabled from the disabled set.
        """
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

    id: str  # exact namespaced toggle identifier for Claude
    name: str  # human-readable short name
    planes: list[str] = field(default_factory=list)
    enabled: bool = True
    status: AuthStatus = AuthStatus.UNKNOWN
    auth: str = ""  # raw auth description from mcp list output
    command: str = ""  # transport/command string (informational)
    extra: dict[str, object] = field(default_factory=dict)  # plane-specific raw data

    @property
    def duplicated(self) -> bool:
        return len(set(self.planes)) > 1

    @property
    def dead(self) -> bool:
        """True only for an ENABLED server whose handshake FAILED.

        The single honest answer to "is this server broken?".  A server the
        owner deliberately disabled is never dead — reporting intentional
        curation as breakage is a false alarm that trains the owner to ignore
        the detector.

        Scope of the `enabled` guard, measured — NOT wider than this:

        * Cross-plane rows: `dead` does return False when ANOTHER plane
          disabled a row whose status is still FAILED, and that is the whole
          of it.  `status._merge_rows` copies the claude-plane `status`
          verbatim, and both UIs key on `row.status.value` rather than on
          `dead`, so such a row still renders "error"/red.  The cross-plane
          case is covered in this predicate ONLY — not in what the owner
          sees.  Settling change, out of scope here and needing its own
          tests: re-label FAILED -> DISABLED in `_merge_rows` when a plane
          disables the row.  Guarded by
          `test_status.py::test_cross_plane_disabled_keeps_failed_status`.
        * `dead` is exposed in `to_dict()` but has NO production consumer:
          `app.py json` builds `ServerInfo` dicts in `core/inventory.py` and
          never calls `ServerRow.to_dict()`.  The change the owner actually
          sees is the `AuthStatus.DISABLED` re-label applied by
          `claude_adapter.reconcile_enabled`, plus the two UI status maps.
        """
        return self.enabled and self.status == AuthStatus.FAILED

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "planes": list(self.planes),
            "enabled": self.enabled,
            "status": self.status.value,
            "auth": self.auth,
            "command": self.command,
            "duplicated": self.duplicated,
            "dead": self.dead,
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
    raw: dict[str, object] = field(default_factory=dict)  # all keys from the file

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "disabled_ids": list(self.disabled_ids),
        }
