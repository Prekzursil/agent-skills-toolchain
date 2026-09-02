"""Throwaway --settings home plugin lifecycle.

Commands mutate only `home`. They never resolve Path.home() or ~/.claude.
Layout (Claude-like settings home that this Linux worktree can actually run):

  settings.json                 winning enabledPlugins map
  .claude.json                  inert trap (must not receive enabledPlugins)
  plugins/installed/<id>/       live payload
  plugins/cache/<id>/<ver>/     version snapshot used by repair
  plugins/rollback/<id>/        previous payload for rollback
  plugins/inventory.json        version + digest journal
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from census import CLAUDE_JSON_REL, INVENTORY_REL, SETTINGS_REL, file_census

PLUGIN_ID = "res0018.fixture.lifecycle"
ENABLED_KEY = "enabledPlugins"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _payload_digest(root: Path) -> str:
    blob = json.dumps(file_census(root), sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def installed_dir(home: Path) -> Path:
    return home / "plugins" / "installed" / PLUGIN_ID


def cache_dir(home: Path, version: str) -> Path:
    return home / "plugins" / "cache" / PLUGIN_ID / version


def rollback_dir(home: Path) -> Path:
    return home / "plugins" / "rollback" / PLUGIN_ID


def seed_empty_home(home: Path, isolation_token: str) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / isolation_token).write_text(isolation_token + "\n", encoding="utf-8")
    _write_json(home / SETTINGS_REL, {"hooks": {}, ENABLED_KEY: {}})
    _write_json(home / CLAUDE_JSON_REL, {"disabledMcpServers": []})
    _write_json(home / INVENTORY_REL, {"plugins": {}})


def current_version(home: Path) -> str | None:
    inv = _read_json(home / INVENTORY_REL)
    row = (inv.get("plugins") or {}).get(PLUGIN_ID) or {}
    ver = row.get("version")
    return str(ver) if ver else None


def _set_enabled(home: Path, enabled: bool) -> None:
    settings = _read_json(home / SETTINGS_REL)
    plugins = dict(settings.get(ENABLED_KEY) or {})
    if enabled:
        plugins[PLUGIN_ID] = True
    else:
        plugins.pop(PLUGIN_ID, None)
    settings[ENABLED_KEY] = plugins
    _write_json(home / SETTINGS_REL, settings)


def _set_inventory(home: Path, version: str | None, digest: str | None) -> None:
    inv = _read_json(home / INVENTORY_REL)
    plugins = dict(inv.get("plugins") or {})
    if version is None:
        plugins.pop(PLUGIN_ID, None)
    else:
        plugins[PLUGIN_ID] = {"id": PLUGIN_ID, "version": version, "digest": digest}
    inv["plugins"] = plugins
    _write_json(home / INVENTORY_REL, inv)


def _snapshot_cache(home: Path, version: str) -> None:
    src = installed_dir(home)
    if src.is_dir():
        _copy_tree(src, cache_dir(home, version))


def install(home: Path, payload: Path, version: str, prior_state_marker: str) -> dict[str, Any]:
    dest = installed_dir(home)
    _copy_tree(payload, dest)
    (dest / "prior-state.txt").write_text(prior_state_marker + "\n", encoding="utf-8")
    _snapshot_cache(home, version)
    digest = _payload_digest(dest)
    _set_enabled(home, True)
    _set_inventory(home, version, digest)
    return {"command": "install", "version": version, "digest": digest}


def update(home: Path, payload: Path, version: str) -> dict[str, Any]:
    prev = current_version(home)
    inst = installed_dir(home)
    if inst.is_dir() and prev:
        _copy_tree(inst, rollback_dir(home))
        (rollback_dir(home) / "FROM_VERSION").write_text(prev + "\n", encoding="utf-8")
    _copy_tree(payload, inst)
    marker_src = cache_dir(home, prev) / "prior-state.txt" if prev else None
    if marker_src and marker_src.is_file():
        shutil.copy2(marker_src, inst / "prior-state.txt")
    _snapshot_cache(home, version)
    digest = _payload_digest(inst)
    _set_enabled(home, True)
    _set_inventory(home, version, digest)
    return {"command": "update", "version": version, "from_version": prev, "digest": digest}


def repair(home: Path) -> dict[str, Any]:
    ver = current_version(home)
    if not ver:
        raise RuntimeError("repair: nothing installed")
    cached = cache_dir(home, ver)
    if not cached.is_dir():
        raise RuntimeError(f"repair: cache missing for {ver}")
    _copy_tree(cached, installed_dir(home))
    digest = _payload_digest(installed_dir(home))
    _set_inventory(home, ver, digest)
    return {"command": "repair", "version": ver, "digest": digest}


def rollback(home: Path) -> dict[str, Any]:
    rb = rollback_dir(home)
    if not rb.is_dir():
        raise RuntimeError("rollback: no previous payload")
    from_ver = (rb / "FROM_VERSION").read_text(encoding="utf-8").strip()
    _copy_tree(rb, installed_dir(home))
    (installed_dir(home) / "FROM_VERSION").unlink(missing_ok=True)
    _snapshot_cache(home, from_ver)
    digest = _payload_digest(installed_dir(home))
    _set_inventory(home, from_ver, digest)
    return {"command": "rollback", "version": from_ver, "digest": digest}


def uninstall(home: Path) -> dict[str, Any]:
    """Remove plugin-owned files, cache, rollback, inventory row, and enabledPlugins."""
    for path in (
        installed_dir(home),
        home / "plugins" / "cache" / PLUGIN_ID,
        rollback_dir(home),
    ):
        if path.exists():
            shutil.rmtree(path)
    for leftover_dir in (
        home / "plugins" / "installed",
        home / "plugins" / "cache",
        home / "plugins" / "rollback",
    ):
        if leftover_dir.is_dir() and not any(leftover_dir.iterdir()):
            leftover_dir.rmdir()
    _set_enabled(home, False)
    _set_inventory(home, None, None)
    return {"command": "uninstall", "version": None}


def naive_uninstall(home: Path) -> dict[str, Any]:
    """BOTH-STATES CONTROL: drop live payload + key, leave cache/prior-state."""
    inst = installed_dir(home)
    if inst.exists():
        shutil.rmtree(inst)
    _set_enabled(home, False)
    return {"command": "naive-uninstall", "left_cache": True}


def inherit_from_cache_if_present(home: Path, payload: Path, version: str) -> str | None:
    """Reinstall helper: leftover cache prior-state.txt is copied (inheritance)."""
    leftover = None
    cache_root = home / "plugins" / "cache" / PLUGIN_ID
    if cache_root.is_dir():
        for marker in sorted(cache_root.rglob("prior-state.txt")):
            leftover = marker.read_text(encoding="utf-8").strip()
            break
    dest = installed_dir(home)
    _copy_tree(payload, dest)
    if leftover:
        (dest / "prior-state.txt").write_text(leftover + "\n", encoding="utf-8")
    digest = _payload_digest(dest)
    _set_enabled(home, True)
    _set_inventory(home, version, digest)
    return leftover
