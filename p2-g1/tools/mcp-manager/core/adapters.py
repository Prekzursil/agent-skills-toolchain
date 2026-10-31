"""Safe write/toggle adapters for the manage-able planes.

Each toggle: backs up the file first, then performs a MINIMAL targeted edit that
preserves all other content. Pure functions over explicit paths — callers (CLI/TUI)
decide when to apply. Never auto-mutates real config on import.

- Claude  : enable/disable = set-membership in projects[path].disabledMcpServers
            (namespaced ids, byte-for-byte; no CLI verb exists for this).
- Codex   : flip [mcp_servers.<name>].enabled via tomlkit (preserves comments/quoting),
            validated by tomllib after write.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import cast


def _backup(path: Path) -> Path:
    bak = path.with_suffix(path.suffix + ".bak")
    _ = shutil.copy2(path, bak)
    return bak


def claude_set_disabled(
    claude_json: Path,
    project_path: str,
    server_id: str,
    disabled: bool,
    *,
    backup: bool = True,
) -> bool:
    """Add/remove server_id in projects[project_path].disabledMcpServers.

    Returns True if a change was written. Preserves all other keys (targeted edit).
    """
    data = cast(
        "dict[str, object]", json.loads(claude_json.read_text(encoding="utf-8"))
    )
    projects = cast("dict[str, object]", data.setdefault("projects", {}))
    block = cast("dict[str, object]", projects.setdefault(project_path, {}))
    arr = cast("list[str]", block.setdefault("disabledMcpServers", []))
    present = server_id in arr
    if disabled and not present:
        arr.append(server_id)
    elif not disabled and present:
        arr[:] = [x for x in arr if x != server_id]
    else:
        return False  # no-op
    if backup:
        _ = _backup(claude_json)
    _ = claude_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True


def codex_set_enabled(
    config_toml: Path, server_name: str, enabled: bool, *, backup: bool = True
) -> bool:
    """Flip [mcp_servers.<name>].enabled via tomlkit; validate with tomllib."""
    import tomlkit  # provided via uv --with tomlkit

    doc = tomlkit.parse(config_toml.read_text(encoding="utf-8"))
    servers = cast(
        "dict[str, object] | None", cast("dict[str, object]", doc).get("mcp_servers")
    )
    if servers is None or server_name not in servers:
        raise KeyError(f"codex server not found: {server_name}")
    table = cast("dict[str, object]", servers[server_name])
    if table.get("enabled", True) == enabled:
        return False  # no-op
    table["enabled"] = enabled
    if backup:
        _ = _backup(config_toml)
    out = tomlkit.dumps(doc)
    # validate before committing the write
    try:
        import tomllib

        _ = tomllib.loads(out)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"refusing to write invalid TOML: {exc}") from exc
    _ = config_toml.write_text(out, encoding="utf-8")
    return True
