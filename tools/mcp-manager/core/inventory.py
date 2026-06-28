"""Cross-plane MCP + skill inventory (read-only).

Foundation shared by mcp-manager (Spec 2 data core), the "prune first" pass
(Spec 3 / council #1 move), and the JIT capability-gateway index. Pure reads —
never mutates Claude/Codex/funnel/plugin state.

Planes scanned:
  - claude-user    : ~/.claude.json  top-level mcpServers + disabledMcpServers
  - claude-project : ~/.claude.json  projects[<path>].{mcpServers,disabledMcpServers,
                     enabledMcpjsonServers,disabledMcpjsonServers}  +  <cwd>/.mcp.json
  - codex          : ~/.codex/config.toml  [mcp_servers.<name>] enabled flag
  - funnel         : ~/.mcp-funnel-master.json servers[]  (+ active .mcp-funnel.json)

Also: duplicate-skill-pack detection over skill roots (the council found three
identical packs: document-skills / example-skills / claude-api).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict, cast

try:  # py3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - env-dependent
    tomllib = None  # type: ignore


class ServerInfo(TypedDict):
    """One server's merged cross-plane inventory (JSON-able)."""

    name: str
    planes: list[str]
    enabled_in: list[str]
    disabled_in: list[str]
    duplicated: bool


class Inventory(TypedDict):
    """Full read-only cross-plane inventory report (JSON-able)."""

    server_count: int
    duplicated_servers: list[str]
    servers: list[ServerInfo]
    duplicate_skill_packs: list[list[str]]


@dataclass
class ServerEntry:
    name: str
    planes: list[str] = field(default_factory=list)  # where it is defined
    enabled_in: list[str] = field(default_factory=list)  # planes where active
    disabled_in: list[str] = field(default_factory=list)  # planes where suppressed

    @property
    def duplicated(self) -> bool:
        return len(self.planes) > 1


def _load_json(path: Path) -> dict[str, object]:
    try:
        return cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def scan_claude(
    claude_json: Path, project_path: str | None = None
) -> dict[str, ServerEntry]:
    """Inventory Claude user + (optionally one) project scope from ~/.claude.json."""
    data = _load_json(claude_json)
    out: dict[str, ServerEntry] = {}

    def ensure(name: str) -> ServerEntry:
        return out.setdefault(name, ServerEntry(name=name))

    user_servers = cast("dict[str, object]", data.get("mcpServers") or {})
    user_disabled = set(cast("list[str]", data.get("disabledMcpServers") or []))
    for name in user_servers:
        e = ensure(name)
        e.planes.append("claude-user")
        (e.disabled_in if name in user_disabled else e.enabled_in).append("claude-user")

    projects = cast("dict[str, object]", data.get("projects") or {})
    target: dict[str, object] = (
        cast("dict[str, object]", projects.get(project_path, {}))
        if project_path
        else {}
    )
    proj_servers = cast("dict[str, object]", target.get("mcpServers") or {})
    proj_disabled = set(cast("list[str]", target.get("disabledMcpServers") or []))
    for name in proj_servers:
        e = ensure(name)
        e.planes.append("claude-project")
        (e.disabled_in if name in proj_disabled else e.enabled_in).append(
            "claude-project"
        )
    return out


def scan_mcp_json(mcp_json: Path) -> dict[str, ServerEntry]:
    """Inventory a project-scope <dir>/.mcp.json ('disabled' flag per server)."""
    data = _load_json(mcp_json)
    out: dict[str, ServerEntry] = {}
    mcp_servers = cast("dict[str, object]", data.get("mcpServers") or {})
    for name, spec in mcp_servers.items():
        e = ServerEntry(name=name, planes=["mcp.json"])
        disabled = (
            isinstance(spec, dict)
            and cast("dict[str, object]", spec).get("disabled") is True
        )
        (e.disabled_in if disabled else e.enabled_in).append("mcp.json")
        out[name] = e
    return out


def scan_codex(config_toml: Path) -> dict[str, ServerEntry]:
    """Inventory Codex ~/.codex/config.toml [mcp_servers.<name>] enabled flag."""
    out: dict[str, ServerEntry] = {}
    if tomllib is None:
        return out
    try:
        data = cast(
            "dict[str, object]",
            tomllib.loads(config_toml.read_text(encoding="utf-8")),
        )
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):  # type: ignore[attr-defined]
        return out
    mcp_servers = cast("dict[str, object]", data.get("mcp_servers") or {})
    for name, spec in mcp_servers.items():
        e = ServerEntry(name=name, planes=["codex"])
        # default enabled unless explicitly false
        enabled = (
            True
            if not isinstance(spec, dict)
            else cast("dict[str, object]", spec).get("enabled", True)
        )
        (e.enabled_in if enabled else e.disabled_in).append("codex")
        out[name] = e
    return out


def scan_funnel(master_json: Path) -> dict[str, ServerEntry]:
    """Inventory funnel master (servers[] list)."""
    data = _load_json(master_json)
    out: dict[str, ServerEntry] = {}
    servers = cast("list[object]", data.get("servers") or [])
    for spec in servers:
        name = (
            cast("dict[str, object]", spec).get("name")
            if isinstance(spec, dict)
            else None
        )
        if not name:
            continue
        name_str = str(name)
        e = ServerEntry(name=name_str, planes=["funnel"], enabled_in=["funnel"])
        out[name_str] = e
    return out


def merge(*inventories: dict[str, ServerEntry]) -> dict[str, ServerEntry]:
    """Union per-plane inventories into one entry per server name."""
    out: dict[str, ServerEntry] = {}
    for inv in inventories:
        for name, e in inv.items():
            tgt = out.setdefault(name, ServerEntry(name=name))
            tgt.planes.extend(e.planes)
            tgt.enabled_in.extend(e.enabled_in)
            tgt.disabled_in.extend(e.disabled_in)
    return out


def find_duplicate_skill_packs(skill_roots: list[Path]) -> list[list[str]]:
    """Group skill packs whose set of skill names is identical (council's 3x packs).

    A 'pack' = an immediate subdirectory of a skill root containing SKILL.md files
    (recursively). Returns groups of >=2 pack paths that expose the SAME skill-name set.
    """
    packs: dict[str, frozenset[str]] = {}
    for root in skill_roots:
        if not root.is_dir():
            continue
        for pack in sorted(p for p in root.iterdir() if p.is_dir()):
            names = frozenset(s.parent.name for s in pack.rglob("SKILL.md"))
            if names:
                packs[str(pack)] = names
    by_signature: dict[frozenset[str], list[str]] = {}
    for path, sig in packs.items():
        by_signature.setdefault(sig, []).append(path)
    return [sorted(paths) for paths in by_signature.values() if len(paths) >= 2]


def build_inventory(home: Path, project_path: str | None = None) -> Inventory:
    """Full read-only inventory against a home dir. Returns a JSON-able dict."""
    inv = merge(
        scan_claude(home / ".claude.json", project_path),
        scan_mcp_json(home / ".mcp.json"),
        scan_codex(home / ".codex" / "config.toml"),
        scan_funnel(home / ".mcp-funnel-master.json"),
    )
    servers: list[ServerInfo] = [
        {
            "name": e.name,
            "planes": list(e.planes),
            "enabled_in": list(e.enabled_in),
            "disabled_in": list(e.disabled_in),
            "duplicated": e.duplicated,
        }
        for e in sorted(inv.values(), key=lambda x: x.name)
    ]
    dup_packs = find_duplicate_skill_packs(
        [
            home / ".claude" / "skills",
            home / ".agents" / "skills",
        ]
    )
    return {
        "server_count": len(servers),
        "duplicated_servers": [s["name"] for s in servers if s["duplicated"]],
        "servers": servers,
        "duplicate_skill_packs": dup_packs,
    }


if __name__ == "__main__":  # pragma: no cover - CLI smoke
    import sys

    rep = build_inventory(Path.home(), project_path=str(Path.home()).replace("\\", "/"))
    json.dump(rep, sys.stdout, indent=2)
