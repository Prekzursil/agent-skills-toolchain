#!/usr/bin/env python3
"""Seed a disposable install target at N-1 plus user-owned files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hashes import inventory, sha256_bytes, snapshot_bytes

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

N1 = "1.0.0"
N = "2.0.0"
PACKAGE = "cnf-0043-fixture"

PLUGIN_RELS = ("plugin/core.py", "plugin/hook.json", "plugin/skill.md")
USER_RELS = ("user/settings.json", "user/notes.md")
PHASES = ("file_copy", "manifest_write", "cache_invalidation")


def _copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes().replace(b"\r\n", b"\n"))


def payload_dir(version: str) -> Path:
    if version == N:
        return FIX / "n"
    if version == N1:
        return FIX / "n1"
    raise ValueError(f"unknown payload version {version}")


def write_payload(root: Path, version: str) -> None:
    src = payload_dir(version)
    _copy_file(src / "core.py", root / "plugin" / "core.py")
    _copy_file(src / "hook.json", root / "plugin" / "hook.json")
    _copy_file(src / "skill.md", root / "plugin" / "skill.md")


def write_manifest(root: Path, version: str) -> None:
    dest = root / "manifest.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "package": PACKAGE,
        "version": version,
        "files": list(PLUGIN_RELS),
    }
    dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def write_cache(root: Path, version: str) -> None:
    core = (root / "plugin" / "core.py").read_bytes().replace(b"\r\n", b"\n")
    cache = root / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    blob = {
        "package": PACKAGE,
        "version": version,
        "core_sha256": sha256_bytes(core),
    }
    (cache / "resolved.json").write_text(
        json.dumps(
            {"package": PACKAGE, "version": version, "blob": f"blobs/{version}.json"},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    blob_dir = cache / "blobs"
    blob_dir.mkdir(parents=True, exist_ok=True)
    (blob_dir / f"{version}.json").write_text(
        json.dumps(blob, indent=2) + "\n", encoding="utf-8"
    )
    # Drop other version blobs so invalidation is a real mutation.
    for stale in blob_dir.glob("*.json"):
        if stale.name != f"{version}.json":
            stale.unlink()


def write_user(root: Path) -> None:
    src = FIX / "user"
    _copy_file(src / "settings.json", root / "user" / "settings.json")
    _copy_file(src / "notes.md", root / "user" / "notes.md")


def seed_pre_upgrade(root: Path) -> dict[str, Any]:
    """Install N-1, user data, manifest, and a warm cache. Returns snapshot."""
    root.mkdir(parents=True, exist_ok=True)
    write_payload(root, N1)
    write_user(root)
    write_manifest(root, N1)
    write_cache(root, N1)
    snap = snapshot_bytes(root)
    inv = inventory(root)
    return {
        "version": N1,
        "upgrade_version": N,
        "package": PACKAGE,
        "file_count": len(inv),
        "plugin_rels": list(PLUGIN_RELS),
        "user_rels": list(USER_RELS),
        "snapshot": snap,
        "inventory": inv,
        "user_sha256": {
            rel: sha256_bytes((root / rel).read_bytes()) for rel in USER_RELS
        },
    }


def read_core_version(root: Path) -> str:
    text = (root / "plugin" / "core.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("VERSION = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise ValueError("VERSION missing from plugin/core.py")
