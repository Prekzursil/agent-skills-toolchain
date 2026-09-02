#!/usr/bin/env python3
"""Content-addressed package cache whose key includes every shipped file.

IMP-0040 (plugin-cache-reaper) and IMP-0463 (package cache invalidation) are
absent on this worktree. This module is the executable SUT for TST-0080:
install a broken package, republish a same-version fix, reinstall, and
observe the fixed bytes because the cache key changed.

A content hash that omits any shipped file is a defect: two packages that
differ only in the omitted file then share one key (see
derive_cache_key_omitting).
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PKG = "pkg.stale-cache-fixture"
VERSION = "1.0.0"
SPEC_VERSION = "1"
ALG = "sha256-canonical-v1"

BROKEN = "BROKEN"
FIXED = "FIXED"

OMIT_PATH = "pkg/extra.dat"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def shipped_inventory(files: dict[str, bytes]) -> list[dict[str, Any]]:
    """Every shipped path participates. Sorted by path so the key is stable."""
    rows: list[dict[str, Any]] = []
    for rel in sorted(files):
        path = str(rel).replace("\\", "/")
        raw = files[rel]
        if not isinstance(raw, (bytes, bytearray)):
            raise TypeError(f"shipped-file-not-bytes:{path}")
        payload = bytes(raw)
        rows.append(
            {
                "path": path,
                "sha256": sha256_bytes(payload),
                "bytes": len(payload),
            }
        )
    return rows


def cache_key_envelope(
    name: str,
    version: str,
    spec_version: str,
    files: dict[str, bytes],
) -> dict[str, Any]:
    inventory = shipped_inventory(files)
    if not inventory:
        raise RuntimeError("package-has-no-shipped-files")
    return {
        "alg": ALG,
        "name": name,
        "version": version,
        "spec_version": spec_version,
        "shipped_files": inventory,
    }


def derive_cache_key(
    name: str,
    version: str,
    spec_version: str,
    files: dict[str, bytes],
) -> str:
    """TST-0080 cache-key derivation (quoted at this def).

    key = sha256( canonical_json({
        alg, name, version, spec_version,
        shipped_files: [{path, sha256, bytes}, ...]  # ALL shipped files, sorted
    }) )

    Name+version alone is not sufficient: a same-version republish must miss.
    Omitting any shipped file from shipped_files is a defect.
    """
    envelope = cache_key_envelope(name, version, spec_version, files)
    blob = canonical_json(envelope).encode("utf-8")
    return sha256_bytes(blob)


def derive_cache_key_omitting(
    name: str,
    version: str,
    spec_version: str,
    files: dict[str, bytes],
    omit_path: str,
) -> str:
    """Known-broken hash: drop one shipped file from the envelope.

    Two packages that differ only in omit_path then collide. This function is
    the detector control, not the shipped install path.
    """
    omit = omit_path.replace("\\", "/")
    reduced = {
        rel: files[rel]
        for rel in files
        if str(rel).replace("\\", "/") != omit
    }
    if len(reduced) == len(files):
        raise KeyError(f"omit-path-absent:{omit}")
    return derive_cache_key(name, version, spec_version, reduced)


def derive_cache_key_name_version(name: str, version: str) -> str:
    """Known-broken hash: name+version only. Same-version republish collides."""
    blob = canonical_json({"name": name, "version": version}).encode("utf-8")
    return sha256_bytes(blob)


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    spec_version: str
    files: dict[str, bytes]

    def inventory(self) -> list[dict[str, Any]]:
        return shipped_inventory(self.files)

    def cache_key(self) -> str:
        return derive_cache_key(
            self.name, self.version, self.spec_version, self.files
        )


def _file(text: str) -> bytes:
    return text.encode("utf-8")


def make_package(*, behavior: str, extra: bytes) -> Package:
    if behavior not in {BROKEN, FIXED}:
        raise ValueError(behavior)
    files = {
        "pkg/__init__.py": _file("# pkg.stale-cache-fixture\n"),
        "pkg/behavior.py": _file(f'BEHAVIOR = "{behavior}"\n'),
        OMIT_PATH: extra,
    }
    return Package(PKG, VERSION, SPEC_VERSION, files)


def broken_package() -> Package:
    return make_package(behavior=BROKEN, extra=b"extra-payload-broken\n")


def fixed_package() -> Package:
    return make_package(behavior=FIXED, extra=b"extra-payload-broken\n")


def extra_mutant(base: Package, extra: bytes) -> Package:
    files = dict(base.files)
    files[OMIT_PATH] = extra
    return Package(base.name, base.version, base.spec_version, files)


def mutate_shipped_byte(base: Package, rel: str) -> Package:
    path = rel.replace("\\", "/")
    if path not in base.files:
        raise KeyError(path)
    raw = bytearray(base.files[path])
    if not raw:
        raise RuntimeError(f"empty-shipped-file:{path}")
    raw[0] = (raw[0] + 1) % 256
    files = dict(base.files)
    files[path] = bytes(raw)
    return Package(base.name, base.version, base.spec_version, files)


class Registry:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._packages: dict[str, Package] = {}

    def publish(self, pkg: Package) -> dict[str, Any]:
        self._packages[pkg.name] = pkg
        dest = self.root / f"{pkg.name}.json"
        meta = {
            "name": pkg.name,
            "version": pkg.version,
            "spec_version": pkg.spec_version,
            "cache_key": pkg.cache_key(),
            "inventory": pkg.inventory(),
        }
        dest.write_text(canonical_json(meta) + "\n", encoding="utf-8")
        blob_dir = self.root / "blobs" / pkg.name
        if blob_dir.exists():
            shutil.rmtree(blob_dir)
        for rel, raw in pkg.files.items():
            out = blob_dir / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(raw)
        return meta

    def get(self, name: str) -> Package:
        pkg = self._packages.get(name)
        if pkg is None:
            raise KeyError(f"package-absent:{name}")
        return pkg


class Client:
    """Shipped client: CAS keyed by derive_cache_key, never by name+version."""

    CACHE_LAYOUT: tuple[dict[str, Any], ...] = (
        {
            "id": "cas",
            "rel": "cas",
            "keying": "sha256-canonical-v1-all-shipped-files",
            "invalidated_on_refresh": True,
        },
        {
            "id": "resolved-index",
            "rel": "index",
            "keying": "cache-key",
            "invalidated_on_refresh": True,
        },
    )

    def __init__(self, registry: Registry, cache_root: Path, profile: Path) -> None:
        self.registry = registry
        self.cache_root = Path(cache_root)
        self.profile = Path(profile)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.profile.mkdir(parents=True, exist_ok=True)

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

    def cas_dir(self, key: str) -> Path:
        return self._path("cas") / key

    def index_path(self, key: str) -> Path:
        return self._path("resolved-index") / f"{key}.json"

    def observe_behavior(self) -> str:
        path = self.profile / "lib" / "pkg" / "behavior.py"
        if not path.is_file():
            raise FileNotFoundError(str(path))
        ns: dict[str, Any] = {}
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), ns, ns)
        return str(ns["BEHAVIOR"])

    def _materialize(self, pkg: Package, dest: Path) -> None:
        if dest.exists():
            shutil.rmtree(dest)
        for rel, raw in pkg.files.items():
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(raw)

    def _copy_cas_to_profile(self, key: str) -> None:
        src = self.cas_dir(key)
        dest = self.profile / "lib"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

    def install(self, name: str) -> dict[str, Any]:
        pkg = self.registry.get(name)
        key = pkg.cache_key()
        cas = self.cas_dir(key)
        idx = self.index_path(key)
        if cas.is_dir() and idx.is_file():
            self._copy_cas_to_profile(key)
            source = "cache"
        else:
            cas.parent.mkdir(parents=True, exist_ok=True)
            self._materialize(pkg, cas)
            idx.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "name": pkg.name,
                "version": pkg.version,
                "spec_version": pkg.spec_version,
                "cache_key": key,
                "inventory": pkg.inventory(),
                "source": "registry",
            }
            idx.write_text(canonical_json(record) + "\n", encoding="utf-8")
            self._copy_cas_to_profile(key)
            source = "registry"
        behavior = self.observe_behavior()
        return {
            "name": pkg.name,
            "version": pkg.version,
            "cache_key": key,
            "source": source,
            "behavior": behavior,
            "inventory": pkg.inventory(),
            "cas_path": str(cas),
            "index_path": str(idx),
        }

    def invalidate(self, name: str) -> dict[str, Any]:
        dropped: list[str] = []
        cas_root = self._path("cas")
        idx_root = self._path("resolved-index")
        if cas_root.is_dir():
            for entry in list(cas_root.iterdir()):
                meta = idx_root / f"{entry.name}.json"
                belongs = False
                if meta.is_file():
                    body = json.loads(meta.read_text(encoding="utf-8"))
                    belongs = body.get("name") == name
                if belongs:
                    shutil.rmtree(entry)
                    meta.unlink(missing_ok=True)
                    dropped.append(entry.name)
        return {"name": name, "dropped_keys": dropped, "count": len(dropped)}

    def cached_keys(self) -> list[str]:
        cas_root = self._path("cas")
        if not cas_root.is_dir():
            return []
        return sorted(p.name for p in cas_root.iterdir() if p.is_dir())


class NameVersionClient(Client):
    """Mutant: cache keyed only by name+version. Same-version republish hits."""

    def install(self, name: str) -> dict[str, Any]:
        pkg = self.registry.get(name)
        key = derive_cache_key_name_version(pkg.name, pkg.version)
        cas = self.cas_dir(key)
        idx = self.index_path(key)
        if cas.is_dir() and idx.is_file():
            self._copy_cas_to_profile(key)
            source = "cache"
        else:
            cas.parent.mkdir(parents=True, exist_ok=True)
            self._materialize(pkg, cas)
            idx.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "name": pkg.name,
                "version": pkg.version,
                "cache_key": key,
                "keying": "name+version",
                "source": "registry",
            }
            idx.write_text(canonical_json(record) + "\n", encoding="utf-8")
            self._copy_cas_to_profile(key)
            source = "registry"
        behavior = self.observe_behavior()
        return {
            "name": pkg.name,
            "version": pkg.version,
            "cache_key": key,
            "source": source,
            "behavior": behavior,
            "cas_path": str(cas),
            "index_path": str(idx),
        }
