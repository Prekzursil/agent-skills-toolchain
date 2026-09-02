"""Throwaway-home settings consumer for this program (RES-0012).

Never reads the live profile. Paths are always the sandbox Estate.
Merge rules:
  * settings.json chain (user < project < local < managed): scalars replace,
    enabledPlugins overlays per id, list keys concatenate.
  * ~/.claude.json is not a settings.json file. disabledMcpServers is honoured
    only under projects[<abs-project>], never at the claude.json root.
  * enabledPlugins / hooks / permissions / model are honoured only from the
    settings.json chain (plus managed-settings.json), never from claude.json.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLUGIN_ID = "probe-plugin@lab"
MCP_ID = "probe-mcp"
MCP_PROJECT_ID = "probe-mcp-project"
TOOL = "Bash"
EVENT = "PreToolUse"


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class Estate:
    home: Path
    project: Path
    managed: Path

    @property
    def project_key(self) -> str:
        return str(self.project.resolve())

    @property
    def user_settings(self) -> Path:
        return self.home / ".claude" / "settings.json"

    @property
    def claude_json(self) -> Path:
        return self.home / ".claude.json"

    @property
    def project_settings(self) -> Path:
        return self.project / ".claude" / "settings.json"

    @property
    def local_settings(self) -> Path:
        return self.project / ".claude" / "settings.local.json"

    @property
    def mcp_json(self) -> Path:
        return self.project / ".mcp.json"

    @property
    def managed_settings(self) -> Path:
        return self.managed / "managed-settings.json"


def new_estate(root: Path) -> Estate:
    root = root.resolve()
    estate = Estate(
        home=root / "home",
        project=root / "project",
        managed=root / "managed",
    )
    estate.home.mkdir(parents=True, exist_ok=True)
    estate.project.mkdir(parents=True, exist_ok=True)
    estate.managed.mkdir(parents=True, exist_ok=True)
    (estate.home / ".claude").mkdir(parents=True, exist_ok=True)
    (estate.project / ".claude").mkdir(parents=True, exist_ok=True)
    return estate


def _concat_list(dst: dict[str, Any], key: str, src: Any) -> None:
    if not isinstance(src, list):
        dst[key] = src
        return
    dst[key] = list(dst.get(key) or []) + list(src)


def merge_settings_layers(layers: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for layer in layers:
        if not layer:
            continue
        if "enabledPlugins" in layer and isinstance(layer["enabledPlugins"], dict):
            merged = dict(out.get("enabledPlugins") or {})
            merged.update(layer["enabledPlugins"])
            out["enabledPlugins"] = merged
        if "hooks" in layer and isinstance(layer["hooks"], dict):
            hooks = dict(out.get("hooks") or {})
            for event, handlers in layer["hooks"].items():
                if isinstance(handlers, list):
                    hooks[event] = list(hooks.get(event) or []) + list(handlers)
                else:
                    hooks[event] = handlers
            out["hooks"] = hooks
        if "permissions" in layer and isinstance(layer["permissions"], dict):
            perms = dict(out.get("permissions") or {})
            for pk, pv in layer["permissions"].items():
                if isinstance(pv, list):
                    perms[pk] = list(perms.get(pk) or []) + list(pv)
                else:
                    perms[pk] = pv
            out["permissions"] = perms
        for key, value in layer.items():
            if key in {"enabledPlugins", "hooks", "permissions"}:
                continue
            if key in {"disabledMcpjsonServers", "enabledMcpjsonServers"}:
                _concat_list(out, key, value)
            else:
                out[key] = value
    return out


def settings_layers(estate: Estate) -> list[dict[str, Any]]:
    return [
        read_json(estate.user_settings),
        read_json(estate.project_settings),
        read_json(estate.local_settings),
        read_json(estate.managed_settings),
    ]


def effective_settings(estate: Estate) -> dict[str, Any]:
    return merge_settings_layers(settings_layers(estate))


def plugin_loaded(estate: Estate, plugin_id: str = PLUGIN_ID) -> bool:
    m = effective_settings(estate).get("enabledPlugins") or {}
    return bool(m.get(plugin_id))


def hook_commands(estate: Estate, event: str = EVENT) -> list[str]:
    cmds: list[str] = []
    for item in (effective_settings(estate).get("hooks") or {}).get(event) or []:
        if isinstance(item, str):
            cmds.append(item)
            continue
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("command"), str):
            cmds.append(item["command"])
        for inner in item.get("hooks") or []:
            if isinstance(inner, dict) and isinstance(inner.get("command"), str):
                cmds.append(inner["command"])
    return cmds


def tool_verdict(estate: Estate, tool: str = TOOL) -> str:
    perms = effective_settings(estate).get("permissions") or {}
    deny = [str(x) for x in (perms.get("deny") or [])]
    allow = [str(x) for x in (perms.get("allow") or [])]
    if any(x == tool or x.startswith(tool + "(") for x in deny):
        return "DENY"
    if any(x == tool or x.startswith(tool + "(") for x in allow):
        return "ALLOW"
    return "ASK"


def selected_model(estate: Estate) -> str | None:
    value = effective_settings(estate).get("model")
    return str(value) if value is not None else None


def _server_ids(blob: dict[str, Any]) -> set[str]:
    servers = blob.get("mcpServers")
    if isinstance(servers, dict):
        return {str(k) for k in servers}
    return set()


def live_mcp(estate: Estate, *, honour_root_disabled: bool = False) -> set[str]:
    """Behaviour: which MCP server ids would be considered live.

    honour_root_disabled=True is the MUTANT that treats claude.json root
    disabledMcpServers as live. Production must leave it False.
    """
    cj = read_json(estate.claude_json)
    user_servers = _server_ids(cj)
    project_mcp = _server_ids(read_json(estate.mcp_json))
    proj = (cj.get("projects") or {}).get(estate.project_key) or {}
    if not isinstance(proj, dict):
        proj = {}
    user_servers |= _server_ids(proj)
    disabled_user = {str(x) for x in (proj.get("disabledMcpServers") or [])}
    if honour_root_disabled:
        disabled_user |= {str(x) for x in (cj.get("disabledMcpServers") or [])}
    live_user = user_servers - disabled_user
    disabled_project = {
        str(x)
        for x in (effective_settings(estate).get("disabledMcpjsonServers") or [])
    }
    live_project = project_mcp - disabled_project
    return live_user | live_project


def mcp_is_live(estate: Estate, server_id: str = MCP_ID, **kwargs) -> bool:
    return server_id in live_mcp(estate, **kwargs)


def behaviour_record(estate: Estate, *, honour_root_disabled: bool = False) -> dict[str, Any]:
    live = sorted(live_mcp(estate, honour_root_disabled=honour_root_disabled))
    hooks = hook_commands(estate)
    rec = {
        "plugin_loaded": plugin_loaded(estate),
        "mcp_live": MCP_ID in live,
        "mcp_project_live": MCP_PROJECT_ID in live,
        "mcp_live_set": live,
        "hook_commands": hooks,
        "tool_verdict": tool_verdict(estate),
        "model": selected_model(estate),
    }
    blob = json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    rec["behaviour_sha256"] = hashlib.sha256(blob).hexdigest()
    return rec


def seed_baseline(estate: Estate) -> None:
    """Minimal live configuration used as the before-state for every delta."""
    write_json(
        estate.user_settings,
        {
            "enabledPlugins": {PLUGIN_ID: True},
            "hooks": {EVENT: [{"command": "res0012-user-hook"}]},
            "permissions": {"allow": [TOOL]},
            "model": "res0012-user-model",
        },
    )
    write_json(
        estate.claude_json,
        {
            "mcpServers": {MCP_ID: {"command": "true", "args": []}},
            "projects": {estate.project_key: {"disabledMcpServers": []}},
        },
    )
    write_json(
        estate.mcp_json,
        {"mcpServers": {MCP_PROJECT_ID: {"command": "true", "args": []}}},
    )
    write_json(estate.project_settings, {})
    write_json(estate.local_settings, {})
    write_json(estate.managed_settings, {})
