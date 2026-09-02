#!/usr/bin/env python3
"""Versioned registry plus client resolution cache with rollback invalidation.

Cache locations are declared on Client.CACHE_LAYOUT and returned by
enumerated_cache_paths(). Callers must use that method; they must not
invent cache directories.

Resolution cache is keyed by package-id (not content hash). A hit is
served without re-reading the registry. That is the stale-cache class:
after rollback, a warm client keeps serving the rolled-away version
unless rollback invalidates the resolution index.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

PKG = "pkg.stale-cache-mirror"
V_RESTORED = "1.0.0"
V_ROLLED_AWAY = "2.0.0"
PAYLOAD_RESTORED = "payload-restored-v1\n"
PAYLOAD_ROLLED_AWAY = "payload-rolled-away-v2\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


class Registry:
    """Marketplace/plugin registry with a snapshot stack for rollback."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.index_path = self.root / "index.json"
        self.snapshots_dir = self.root / "snapshots"
        self.root.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.is_file():
            self._write_index({"packages": {}})

    def _write_index(self, doc: dict[str, Any]) -> None:
        self.index_path.write_text(canonical(doc), encoding="utf-8")

    def current(self) -> dict[str, Any]:
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def get(self, name: str) -> dict[str, Any] | None:
        pkg = (self.current().get("packages") or {}).get(name)
        return dict(pkg) if isinstance(pkg, dict) else None

    def _snapshot(self) -> None:
        n = len(list(self.snapshots_dir.glob("snap-*.json")))
        dest = self.snapshots_dir / f"snap-{n:04d}.json"
        dest.write_text(self.index_path.read_text(encoding="utf-8"), encoding="utf-8")

    def publish(self, name: str, version: str, payload: str) -> dict[str, Any]:
        self._snapshot()
        entry = {
            "name": name,
            "version": version,
            "payload": payload,
            "digest": sha256_text(payload),
        }
        doc = self.current()
        packages = dict(doc.get("packages") or {})
        packages[name] = entry
        doc["packages"] = packages
        self._write_index(doc)
        return dict(entry)

    def rollback(self) -> dict[str, Any]:
        snaps = sorted(self.snapshots_dir.glob("snap-*.json"))
        if not snaps:
            raise RuntimeError("no-registry-snapshot")
        latest = snaps[-1]
        restored = json.loads(latest.read_text(encoding="utf-8"))
        self._write_index(restored)
        latest.unlink()
        return restored


class Client:
    """One client's on-disk caches. Layout is the implementation, not the probe."""

    CACHE_LAYOUT: tuple[dict[str, Any], ...] = (
        {
            "id": "resolved-index",
            "rel": "resolved-index",
            "keying": "package-id",
            "invalidated_on_rollback": True,
        },
        {
            "id": "cas-blobs",
            "rel": "cas",
            "keying": "sha256-of-payload",
            "invalidated_on_rollback": False,
        },
    )

    def __init__(self, registry: Registry, cache_root: Path) -> None:
        self.registry = registry
        self.cache_root = Path(cache_root)
        self.cache_root.mkdir(parents=True, exist_ok=True)

    def enumerated_cache_paths(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for spec in self.CACHE_LAYOUT:
            item = dict(spec)
            item["path"] = str((self.cache_root / spec["rel"]).resolve())
            rows.append(item)
        return rows

    def _path(self, cache_id: str) -> Path:
        for spec in self.enumerated_cache_paths():
            if spec["id"] == cache_id:
                return Path(spec["path"])
        raise KeyError(cache_id)

    def invalidate_rollback_caches(self) -> list[str]:
        dropped: list[str] = []
        for spec in self.enumerated_cache_paths():
            if not spec.get("invalidated_on_rollback"):
                continue
            p = Path(spec["path"])
            if p.exists():
                shutil.rmtree(p)
                dropped.append(spec["id"])
        return dropped

    def cache_entry_state(self, name: str) -> dict[str, Any]:
        idx = self._path("resolved-index") / f"{name}.json"
        if not idx.is_file():
            return {"present": False, "path": str(idx)}
        body = json.loads(idx.read_text(encoding="utf-8"))
        return {
            "present": True,
            "path": str(idx),
            "version": body.get("version"),
            "digest": body.get("digest"),
            "source_recorded": body.get("source"),
        }

    def resolve(self, name: str) -> dict[str, Any]:
        idx_dir = self._path("resolved-index")
        cached = idx_dir / f"{name}.json"
        if cached.is_file():
            body = json.loads(cached.read_text(encoding="utf-8"))
            return {
                "name": name,
                "version": body["version"],
                "digest": body["digest"],
                "payload": body.get("payload"),
                "source": "cache",
                "cache_path": str(cached),
            }
        pkg = self.registry.get(name)
        if pkg is None:
            raise KeyError(f"package-absent:{name}")
        cas_dir = self._path("cas-blobs")
        cas_dir.mkdir(parents=True, exist_ok=True)
        blob = cas_dir / pkg["digest"]
        blob.write_text(pkg["payload"], encoding="utf-8")
        idx_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "name": name,
            "version": pkg["version"],
            "digest": pkg["digest"],
            "payload": pkg["payload"],
            "source": "registry",
        }
        cached.write_text(canonical(record), encoding="utf-8")
        return {
            "name": name,
            "version": pkg["version"],
            "digest": pkg["digest"],
            "payload": pkg["payload"],
            "source": "registry",
            "cache_path": str(cached),
        }


def rollback_registry(
    registry: Registry,
    clients: list[Client],
    *,
    invalidate: bool,
) -> dict[str, Any]:
    restored = registry.rollback()
    dropped: list[dict[str, Any]] = []
    if invalidate:
        for client in clients:
            dropped.append(
                {
                    "cache_root": str(client.cache_root),
                    "dropped": client.invalidate_rollback_caches(),
                    "enumerated": client.enumerated_cache_paths(),
                }
            )
    return {"registry": restored, "invalidated": invalidate, "clients": dropped}
