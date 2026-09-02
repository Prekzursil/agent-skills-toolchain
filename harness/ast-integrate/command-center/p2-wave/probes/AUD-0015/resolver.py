"""MCP enabled-state resolver across four config surfaces.

Measured precedent (AUD-0015 inputs): a root-scope disabledMcpServers key is
inert; the effective disable lives on the ~/.claude.json per-project block.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from reader import load_json_scoped, sanitize_server_map

SURFACE_HOME_MCP = "home_mcp_json"
SURFACE_CLAUDE_ROOT = "claude_root"
SURFACE_CLAUDE_PROJECT = "claude_project"
SURFACE_SETTINGS = "settings_json"

WIN_PROJECT_DISABLE = "claude.json:projects[].disabledMcpServers"
WIN_SETTINGS_DISABLE = "settings.json:enabledMcpjsonServers"
WIN_HOME_MCP = "~/.mcp.json:mcpServers"
WIN_ROOT_SERVERS = "~/.claude.json:root.mcpServers"
WIN_PROJECT_SERVERS = "~/.claude.json:projects[].mcpServers"
WIN_ROOT_INERT = "~/.claude.json:root.disabledMcpServers (inert)"
WIN_UNDECLARED = "undeclared"


def disabled_names(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(x) for x in value if x is not None and str(x)}
    if isinstance(value, dict):
        out = set()
        for key, flag in value.items():
            if flag is False or flag == 0 or flag == "false":
                continue
            if flag:
                out.add(str(key))
        return out
    return set()


def enable_map(value: Any) -> dict[str, bool | None]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, bool | None] = {}
    for key, flag in value.items():
        if flag is True or flag == 1 or flag == "true":
            out[str(key)] = True
        elif flag is False or flag == 0 or flag == "false":
            out[str(key)] = False
        else:
            out[str(key)] = None
    return out


def match_project(projects: dict, cwd: Path) -> tuple[str | None, dict]:
    if not isinstance(projects, dict) or not projects:
        return None, {}
    candidates = []
    for item in (cwd, Path(os.path.abspath(str(cwd)))):
        text = str(item)
        candidates.extend([text, text.rstrip("/\\")])
    seen = []
    for cand in candidates:
        if cand in seen:
            continue
        seen.append(cand)
        body = projects.get(cand)
        if isinstance(body, dict):
            return cand, body
    cwd_abs = os.path.abspath(str(cwd))
    for key, body in projects.items():
        if not isinstance(body, dict):
            continue
        try:
            if os.path.abspath(str(key)) == cwd_abs:
                return str(key), body
        except OSError:
            continue
    return None, {}


def live_paths(home: Path | None = None, cwd: Path | None = None) -> dict[str, Path]:
    home = Path(home or Path.home())
    cwd = Path(cwd or Path("/opt/p2/ast-integrate"))
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    claude_dir = Path(cfg) if cfg else home / ".claude"
    return {
        "home": home,
        "cwd": cwd,
        "home_mcp_json": home / ".mcp.json",
        "claude_json": home / ".claude.json",
        "settings_json": claude_dir / "settings.json",
    }


def load_surfaces(
    home_mcp: Path,
    claude_json: Path,
    settings_json: Path,
    cwd: Path,
) -> dict[str, Any]:
    mcp = load_json_scoped(home_mcp)
    claude = load_json_scoped(claude_json)
    settings = load_json_scoped(settings_json)
    payload = claude.get("payload") or {}
    projects = payload.get("projects") if isinstance(payload, dict) else {}
    matched_key, project_body = match_project(projects or {}, cwd)
    return {
        SURFACE_HOME_MCP: mcp,
        SURFACE_CLAUDE_ROOT: {
            "file": claude,
            "mcpServers": sanitize_server_map((payload or {}).get("mcpServers")),
            "disabledMcpServers": (payload or {}).get("disabledMcpServers"),
            "enabledMcpServers": (payload or {}).get("enabledMcpServers"),
        },
        SURFACE_CLAUDE_PROJECT: {
            "matched_key": matched_key,
            "status": (
                "ABSENT"
                if claude.get("status") == "ABSENT"
                else ("UNMATCHED" if matched_key is None else "PRESENT")
            ),
            "mcpServers": sanitize_server_map((project_body or {}).get("mcpServers")),
            "disabledMcpServers": (project_body or {}).get("disabledMcpServers"),
            "enabledMcpServers": (project_body or {}).get("enabledMcpServers"),
        },
        SURFACE_SETTINGS: settings,
        "cwd": str(cwd),
    }


def _declared_maps(surfaces: dict) -> dict[str, dict[str, dict]]:
    home_payload = (surfaces[SURFACE_HOME_MCP].get("payload") or {})
    settings_payload = (surfaces[SURFACE_SETTINGS].get("payload") or {})
    return {
        SURFACE_HOME_MCP: sanitize_server_map(home_payload.get("mcpServers")),
        SURFACE_CLAUDE_ROOT: surfaces[SURFACE_CLAUDE_ROOT].get("mcpServers") or {},
        SURFACE_CLAUDE_PROJECT: surfaces[SURFACE_CLAUDE_PROJECT].get("mcpServers") or {},
        SURFACE_SETTINGS: sanitize_server_map(settings_payload.get("mcpServers")),
    }


def resolve_servers(surfaces: dict, treat_root_disable_as_effective: bool = False) -> list[dict]:
    maps = _declared_maps(surfaces)
    root_disabled = disabled_names(surfaces[SURFACE_CLAUDE_ROOT].get("disabledMcpServers"))
    project_disabled = disabled_names(
        surfaces[SURFACE_CLAUDE_PROJECT].get("disabledMcpServers")
    )
    settings_payload = surfaces[SURFACE_SETTINGS].get("payload") or {}
    settings_flags = enable_map(settings_payload.get("enabledMcpjsonServers"))

    names = set()
    for block in maps.values():
        names.update(block)
    names.update(root_disabled)
    names.update(project_disabled)
    names.update(settings_flags)

    rows = []
    for name in sorted(names):
        declared_on = [surf for surf, block in maps.items() if name in block]
        root_listed = name in root_disabled
        proj_listed = name in project_disabled
        settings_flag = settings_flags.get(name)
        if treat_root_disable_as_effective:
            effective = not (root_listed or proj_listed)
            if settings_flag is False:
                effective = False
            if not declared_on and not root_listed and not proj_listed and settings_flag is None:
                effective = None
            winner = "naive-union-disable"
        elif proj_listed:
            effective = False
            winner = WIN_PROJECT_DISABLE
        elif settings_flag is False:
            effective = False
            winner = WIN_SETTINGS_DISABLE
        elif not declared_on:
            effective = None
            winner = WIN_ROOT_INERT if root_listed else WIN_UNDECLARED
        else:
            effective = True
            if SURFACE_HOME_MCP in declared_on:
                winner = WIN_HOME_MCP
            elif SURFACE_CLAUDE_ROOT in declared_on:
                winner = WIN_ROOT_SERVERS
            elif SURFACE_CLAUDE_PROJECT in declared_on:
                winner = WIN_PROJECT_SERVERS
            else:
                winner = WIN_HOME_MCP
        rows.append(
            {
                "name": name,
                "declared_on": declared_on,
                "root_disabled_listed": root_listed,
                "root_disabled_inert": root_listed and not treat_root_disable_as_effective,
                "project_disabled": proj_listed,
                "settings_enabledMcpjsonServers": settings_flag,
                "effective_enabled": effective,
                "winning_surface": winner,
            }
        )
    return rows


def resolve_estate(
    home: Path,
    cwd: Path,
    treat_root_disable_as_effective: bool = False,
) -> dict[str, Any]:
    paths = live_paths(home=home, cwd=cwd)
    surfaces = load_surfaces(
        paths["home_mcp_json"],
        paths["claude_json"],
        paths["settings_json"],
        cwd,
    )
    servers = resolve_servers(
        surfaces, treat_root_disable_as_effective=treat_root_disable_as_effective
    )
    return {
        "paths": {k: str(v) for k, v in paths.items()},
        "surfaces": {
            SURFACE_HOME_MCP: {
                "status": surfaces[SURFACE_HOME_MCP]["status"],
                "bytes": surfaces[SURFACE_HOME_MCP]["bytes"],
                "mcp_keys": surfaces[SURFACE_HOME_MCP]["mcp_keys"],
                "parse_error": surfaces[SURFACE_HOME_MCP]["parse_error"],
                "server_names": sorted(
                    (surfaces[SURFACE_HOME_MCP].get("payload") or {}).get("mcpServers") or {}
                ),
            },
            SURFACE_CLAUDE_ROOT: {
                "file_status": surfaces[SURFACE_CLAUDE_ROOT]["file"]["status"],
                "bytes": surfaces[SURFACE_CLAUDE_ROOT]["file"]["bytes"],
                "server_names": sorted(surfaces[SURFACE_CLAUDE_ROOT].get("mcpServers") or {}),
                "disabled": sorted(
                    disabled_names(surfaces[SURFACE_CLAUDE_ROOT].get("disabledMcpServers"))
                ),
            },
            SURFACE_CLAUDE_PROJECT: {
                "status": surfaces[SURFACE_CLAUDE_PROJECT]["status"],
                "matched_key": surfaces[SURFACE_CLAUDE_PROJECT]["matched_key"],
                "server_names": sorted(surfaces[SURFACE_CLAUDE_PROJECT].get("mcpServers") or {}),
                "disabled": sorted(
                    disabled_names(surfaces[SURFACE_CLAUDE_PROJECT].get("disabledMcpServers"))
                ),
            },
            SURFACE_SETTINGS: {
                "status": surfaces[SURFACE_SETTINGS]["status"],
                "bytes": surfaces[SURFACE_SETTINGS]["bytes"],
                "mcp_keys": surfaces[SURFACE_SETTINGS]["mcp_keys"],
                "parse_error": surfaces[SURFACE_SETTINGS]["parse_error"],
                "enabledMcpjsonServers": enable_map(
                    (surfaces[SURFACE_SETTINGS].get("payload") or {}).get(
                        "enabledMcpjsonServers"
                    )
                ),
                "server_names": sorted(
                    (surfaces[SURFACE_SETTINGS].get("payload") or {}).get("mcpServers")
                    or {}
                ),
            },
        },
        "servers": servers,
        "by_name": {row["name"]: row for row in servers},
        "treat_root_disable_as_effective": treat_root_disable_as_effective,
    }


def disagreements(servers: list[dict]) -> list[dict]:
    rows = []
    for rec in servers:
        flags = []
        if rec.get("root_disabled_listed") and rec.get("effective_enabled") is True:
            flags.append("root-disable-inert-vs-effective-enabled")
        if rec.get("project_disabled") and rec.get("effective_enabled") is not False:
            flags.append("project-disable-did-not-win")
        if rec.get("root_disabled_listed") and rec.get("project_disabled"):
            flags.append("root-and-project-both-list")
        declared = rec.get("declared_on") or []
        if len(declared) > 1:
            flags.append("declared-on-multiple-surfaces")
        if rec.get("settings_enabledMcpjsonServers") is False and rec.get("effective_enabled") is True:
            flags.append("settings-false-but-enabled")
        if flags:
            rows.append({"name": rec["name"], "flags": flags, "record": rec})
    return rows
