"""Loadout — read/write ~/.claude/.mcp-disabled-defaults.json.

This file is the loadout-defaults store: a list of server IDs that should be
disabled by default when a new project starts.  It mirrors the shape of
projects[path].disabledMcpServers in ~/.claude.json.

File shape:
    {
        "_comment": "...",
        "disabledMcpServers": ["id1", "id2", ...]
    }

The caller decides when to apply the loadout (e.g. via claude_adapter.set_server_disabled).
This module ONLY manages the loadout store itself.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import cast

from .models import Loadout

_DEFAULTS_PATH = Path.home() / ".claude" / ".mcp-disabled-defaults.json"
_KEY = "disabledMcpServers"


def _load_raw(path: Path) -> dict[str, object]:
    try:
        return cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _backup(path: Path) -> Path:
    bak_dir = path.parent / ".mcp-manager-backups"
    bak_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    bak = bak_dir / f"{path.name}.{ts}.bak"
    _ = shutil.copy2(path, bak)
    return bak


def read_loadout(path: Path = _DEFAULTS_PATH) -> Loadout:
    """Read the loadout from the defaults file.

    Returns a Loadout with an empty disabled_ids list if the file is missing
    or malformed (fail-open for reads).
    """
    raw = _load_raw(path)
    ids = raw.get(_KEY)
    disabled = list(cast("list[str]", ids)) if isinstance(ids, list) else []
    return Loadout(name="defaults", disabled_ids=disabled, raw=raw)


def write_loadout(
    loadout: Loadout,
    path: Path = _DEFAULTS_PATH,
    *,
    backup: bool = True,
) -> None:
    """Write the loadout back to the defaults file.

    Merges with any existing unknown keys so that hand-edited comments and
    fields (e.g. '_comment', '_tier1_enabled') are preserved.
    """
    raw = _load_raw(path)
    if backup and path.exists():
        _ = _backup(path)
    raw[_KEY] = list(loadout.disabled_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")


def add_to_loadout(
    server_id: str,
    path: Path = _DEFAULTS_PATH,
    *,
    backup: bool = True,
) -> bool:
    """Add server_id to the disabled defaults. Returns True if changed."""
    loadout = read_loadout(path)
    if server_id in loadout.disabled_ids:
        return False
    loadout.disabled_ids.append(server_id)
    write_loadout(loadout, path, backup=backup)
    return True


def remove_from_loadout(
    server_id: str,
    path: Path = _DEFAULTS_PATH,
    *,
    backup: bool = True,
) -> bool:
    """Remove server_id from the disabled defaults. Returns True if changed."""
    loadout = read_loadout(path)
    if server_id not in loadout.disabled_ids:
        return False
    loadout.disabled_ids = [x for x in loadout.disabled_ids if x != server_id]
    write_loadout(loadout, path, backup=backup)
    return True


def apply_loadout_to_project(
    loadout: Loadout,
    claude_json: Path,
    project_path: str,
    *,
    backup_dir: Path | None = None,
) -> list[str]:
    """Disable every server in loadout.disabled_ids for the given project.

    Uses claude_adapter.set_server_disabled for each id (safe write logic).
    Returns a list of IDs that were actually changed (i.e. were not already disabled).

    This is a convenience wrapper; callers may also iterate themselves.
    """
    from . import claude_adapter  # deferred to avoid circular

    changed: list[str] = []
    for sid in loadout.disabled_ids:
        if claude_adapter.set_server_disabled(
            claude_json,
            project_path,
            sid,
            True,
            backup_dir=backup_dir,
            _mtime_check=False,  # batch; caller is responsible for single backup
        ):
            changed.append(sid)
    return changed
