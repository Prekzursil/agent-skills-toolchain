#!/usr/bin/env python3
"""Rollback-rehearsal: execute restore from a packaged artifact.

User-data paths present before rollback must exist afterwards with the same
sha256. A naive wipe-the-profile rollback is the both-states control that
must lose the planted file.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

USER_DATA_DIR = "user-data"
PLUGIN_DIR = "plugin"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def inventory_user_data(profile: Path) -> dict[str, str]:
    root = profile / USER_DATA_DIR
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = sha256_bytes(path.read_bytes())
    return out


def install_package(package: Path, profile: Path) -> None:
    dest = profile / PLUGIN_DIR
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package) as zf:
        zf.extractall(dest)


def plugin_manifest(profile: Path) -> dict[str, Any]:
    path = profile / PLUGIN_DIR / "plugin.json"
    return json.loads(path.read_text(encoding="utf-8"))


def plant_user_data(profile: Path, rel: str, payload: bytes) -> Path:
    path = profile / USER_DATA_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def execute_rollback(package: Path, profile: Path) -> dict[str, Any]:
    """Restore plugin/ from the packaged artifact. Do not touch user-data/."""
    before = inventory_user_data(profile)
    plugin = profile / PLUGIN_DIR
    if plugin.exists():
        shutil.rmtree(plugin)
    install_package(package, profile)
    after = inventory_user_data(profile)
    lost = sorted(set(before) - set(after))
    changed = sorted(k for k in before if k in after and before[k] != after[k])
    ok = not lost and not changed
    return {
        "ok": ok,
        "mode": "packaged-artifact-restore",
        "package": package.as_posix(),
        "before": before,
        "after": after,
        "lost": lost,
        "changed": changed,
        "plugin_version": plugin_manifest(profile).get("version"),
    }


def naive_rollback(package: Path, profile: Path) -> dict[str, Any]:
    """Destructive control: wipe the whole profile then reinstall the package."""
    before = inventory_user_data(profile)
    if profile.exists():
        shutil.rmtree(profile)
    profile.mkdir(parents=True, exist_ok=True)
    install_package(package, profile)
    after = inventory_user_data(profile)
    lost = sorted(set(before) - set(after))
    return {
        "ok": False,
        "mode": "naive-wipe-profile",
        "package": package.as_posix(),
        "before": before,
        "after": after,
        "lost": lost,
        "plugin_version": plugin_manifest(profile).get("version")
        if (profile / PLUGIN_DIR / "plugin.json").is_file()
        else None,
    }


def rehearse(
    v1_package: Path,
    v2_package: Path,
    profile: Path,
    planted_rel: str,
    planted_payload: bytes,
) -> dict[str, Any]:
    """Install v1, plant user data, upgrade to v2, roll back to v1 package."""
    if profile.exists():
        shutil.rmtree(profile)
    profile.mkdir(parents=True)
    install_package(v1_package, profile)
    planted = plant_user_data(profile, planted_rel, planted_payload)
    planted_hash = sha256_bytes(planted_payload)
    install_package(v2_package, profile)
    mid = plugin_manifest(profile)
    result = execute_rollback(v1_package, profile)
    exists = planted.is_file()
    live_hash = sha256_bytes(planted.read_bytes()) if exists else None
    result.update(
        {
            "planted_path": planted.as_posix(),
            "planted_rel": planted_rel,
            "planted_hash": planted_hash,
            "live_hash": live_hash,
            "exists_after": exists,
            "hash_match": exists and live_hash == planted_hash,
            "upgraded_to": mid.get("version"),
            "rolled_back_to": result.get("plugin_version"),
            "pass": bool(result.get("ok") and exists and live_hash == planted_hash),
        }
    )
    return result
