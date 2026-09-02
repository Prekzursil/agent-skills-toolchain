"""Hermetic in-place upgrade of the user-owned settings surface (TST-0071).

Estate precedent: a root-scoped disabledMcpServers / enabledPlugins dump is
inert. Live curation lives per-project (.mcp.json) and in settings.json.
A schema rename must relocate those values, never wipe them.

This sparse worktree has no packaged plugin upgrade CLI. The operator here
is the versioned settings-upgrade contract the catalog names: upgrade from
each supported prior layout to current and keep every user-authored key.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CURRENT_VERSION = "3"
SUPPORTED_PRIOR = ("1", "2")
LAYOUT_FILE = "layout-version"
CLAUDE = "claude.json"
SETTINGS = "settings.json"
MCP = "projects/demo/.mcp.json"

USER_MODEL = "opus-user-choice"
USER_THEME = "solarized"
USER_DISABLED = ["hacktricks-mcp", "user-custom-mcp"]
USER_PLUGINS = {"ast-plugin": True, "user-plugin": False}
USER_CUSTOM = {"user.note": "keep-me", "user.workflow": "my-pipeline"}
USER_PERMISSIONS = {"allow": ["Read", "Grep"]}
USER_SERVERS = {
    "hacktricks-mcp": {"command": "npx", "args": ["hacktricks-mcp"]},
    "user-custom-mcp": {"command": "uvx", "args": ["user-mcp"]},
}


def dump(doc: Any) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(doc), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not a JSON object")
    return doc


def read_version(root: Path) -> str:
    path = root / LAYOUT_FILE
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    claude = load_json(root / CLAUDE)
    ver = claude.get("schema_version")
    if isinstance(ver, int) and ver >= 1:
        return str(ver)
    return "1"


def write_version(root: Path, version: str) -> None:
    (root / LAYOUT_FILE).write_text(version + "\n", encoding="utf-8")


def _nested(doc: dict[str, Any], keys: list[str]) -> Any:
    cur: Any = doc
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def seed_profile(root: Path, version: str) -> Path:
    """Plant a user-authored profile at a supported layout version."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    version = str(version)
    if version == "1":
        write_json(
            root / CLAUDE,
            {
                "schema_version": 1,
                "model": USER_MODEL,
                "userTheme": USER_THEME,
                "permissions": USER_PERMISSIONS,
                "disabledMcpServers": list(USER_DISABLED),
                "enabledPlugins": dict(USER_PLUGINS),
                "mcpServers": json.loads(json.dumps(USER_SERVERS)),
                "customEntries": dict(USER_CUSTOM),
            },
        )
    elif version == "2":
        write_json(
            root / CLAUDE,
            {
                "schema_version": 2,
                "model": USER_MODEL,
                "userTheme": USER_THEME,
                "permissions": USER_PERMISSIONS,
                "customEntries": dict(USER_CUSTOM),
            },
        )
        write_json(root / SETTINGS, {"schema_version": 2, "enabledPlugins": dict(USER_PLUGINS)})
        write_json(
            root / MCP,
            {
                "schema_version": 2,
                "disabledMcpServers": list(USER_DISABLED),
                "mcpServers": json.loads(json.dumps(USER_SERVERS)),
            },
        )
    elif version == "3":
        write_json(
            root / CLAUDE,
            {
                "schema_version": 3,
                "model": USER_MODEL,
                "userTheme": USER_THEME,
                "permissions": USER_PERMISSIONS,
                "userCustom": dict(USER_CUSTOM),
            },
        )
        write_json(
            root / SETTINGS,
            {
                "schema_version": 3,
                "pluginCuration": {"enabled": dict(USER_PLUGINS)},
            },
        )
        write_json(
            root / MCP,
            {
                "schema_version": 3,
                "mcpCuration": {"disabled": list(USER_DISABLED)},
                "mcpServers": json.loads(json.dumps(USER_SERVERS)),
            },
        )
    else:
        raise ValueError(f"unsupported seed version {version}")
    write_version(root, version)
    return root


def extract_intent(root: Path) -> dict[str, Any]:
    """Canonical user-authored settings, independent of on-disk schema version."""
    claude = load_json(root / CLAUDE)
    settings = load_json(root / SETTINGS)
    mcp = load_json(root / MCP)
    disabled = (
        _nested(mcp, ["mcpCuration", "disabled"])
        or mcp.get("disabledMcpServers")
        or claude.get("disabledMcpServers")
        or []
    )
    plugins = (
        _nested(settings, ["pluginCuration", "enabled"])
        or settings.get("enabledPlugins")
        or claude.get("enabledPlugins")
        or {}
    )
    custom = claude.get("userCustom") or claude.get("customEntries") or {}
    servers = mcp.get("mcpServers") or claude.get("mcpServers") or {}
    theme = claude.get("userTheme") or settings.get("userTheme")
    return {
        "mcp.disabled": list(disabled),
        "mcp.servers": servers,
        "plugins.enabled": plugins,
        "custom": custom,
        "model": claude.get("model"),
        "permissions": claude.get("permissions"),
        "userTheme": theme,
    }


def intent_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return json.loads(dump(a)) == json.loads(dump(b))


def lost_intent_keys(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    lost: list[str] = []
    for key, value in before.items():
        if key not in after:
            lost.append(key)
            continue
        if json.loads(dump(after[key])) != json.loads(dump(value)):
            lost.append(key)
    return lost


def _migrate_v1_to_v2(root: Path) -> None:
    claude = load_json(root / CLAUDE)
    settings = load_json(root / SETTINGS)
    mcp = load_json(root / MCP)

    plugins = claude.pop("enabledPlugins", None)
    if plugins is not None:
        settings["enabledPlugins"] = plugins
    disabled = claude.pop("disabledMcpServers", None)
    if disabled is not None:
        mcp["disabledMcpServers"] = disabled
    servers = claude.pop("mcpServers", None)
    if servers is not None:
        mcp["mcpServers"] = servers

    claude["schema_version"] = 2
    settings["schema_version"] = 2
    mcp["schema_version"] = 2
    write_json(root / CLAUDE, claude)
    write_json(root / SETTINGS, settings)
    write_json(root / MCP, mcp)
    write_version(root, "2")


def _migrate_v2_to_v3(root: Path, *, wipe_curation: bool) -> None:
    claude = load_json(root / CLAUDE)
    settings = load_json(root / SETTINGS)
    mcp = load_json(root / MCP)

    plugins = settings.pop("enabledPlugins", None)
    if plugins is None:
        plugins = claude.pop("enabledPlugins", {}) or {}
    disabled = mcp.pop("disabledMcpServers", None)
    if disabled is None:
        disabled = claude.pop("disabledMcpServers", []) or []
    custom = claude.pop("customEntries", None)
    if custom is None:
        custom = claude.get("userCustom") or {}

    if wipe_curation:
        plugins = {}
        disabled = []
        custom = {}

    settings["pluginCuration"] = {"enabled": plugins}
    mcp["mcpCuration"] = {"disabled": list(disabled)}
    claude["userCustom"] = custom
    claude["schema_version"] = 3
    settings["schema_version"] = 3
    mcp["schema_version"] = 3
    write_json(root / CLAUDE, claude)
    write_json(root / SETTINGS, settings)
    write_json(root / MCP, mcp)
    write_version(root, "3")


def upgrade(
    root: Path,
    target: str = CURRENT_VERSION,
    *,
    wipe_curation: bool = False,
) -> dict[str, Any]:
    root = Path(root)
    started = read_version(root)
    target = str(target)
    steps: list[str] = []
    current = started
    if int(current) < 2 <= int(target):
        _migrate_v1_to_v2(root)
        steps.append("v1-to-v2-relocate-live-curation")
        current = "2"
    if int(current) < 3 <= int(target):
        _migrate_v2_to_v3(root, wipe_curation=wipe_curation)
        steps.append("v2-to-v3-schema-rename")
        current = "3"
    return {
        "status": "already-current" if not steps else "upgraded",
        "from_version": started,
        "target_version": target,
        "current_version": read_version(root),
        "steps": steps,
        "wipe_curation": wipe_curation,
    }
