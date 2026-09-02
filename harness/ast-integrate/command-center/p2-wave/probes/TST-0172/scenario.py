#!/usr/bin/env python3
"""Live measurements for TST-0172: cache key is content hash, not name+version.

SUT: tools/marketplace/package_cache.py ContentAddressedPackageCache.
Catalog question: a same-version republish must be fetched, not served stale.
Both-states: an unchanged package IS served from cache (the cache still works).
Regression seed: a name+version key masks the republished fix.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.package_cache import (  # noqa: E402
    CacheError,
    ContentAddressedPackageCache,
    Observation,
    content_digest,
)

UNIT = "TST-0172"
PACKAGE = "tst0172-cache-pkg"
VERSION = "1.0.0"
BUGGY = b"TST-0172-BUGGY-SAME-VERSION\n"
FIXED = b"TST-0172-FIXED-SAME-VERSION\n"
IMPL = "tools/marketplace/package_cache.py"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _install(dest: Path, payload: bytes) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(payload)
    live = dest.read_bytes()
    return {
        "path": dest.as_posix(),
        "exists": dest.is_file(),
        "bytes": len(live),
        "sha256": sha256_hex(live),
        "equals_payload": live == payload,
    }


class NameVersionKeyedCache:
    """Regression mutant: key is name@version. Same-version republish is masked."""

    def __init__(self) -> None:
        self.source: dict[tuple[str, str], bytes] = {}
        self.cache: dict[str, bytes] = {}
        self.observe_count = 0
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(name: str, version: str) -> str:
        return f"{name}@{version}"

    def publish(self, name: str, payload: bytes, version: str) -> dict[str, Any]:
        if not payload:
            raise CacheError("empty payload")
        self.source[(name, version)] = payload
        return {
            "name": name,
            "version": version,
            "digest": content_digest(payload),
            "cache_key": self.key(name, version),
            "bytes": len(payload),
        }

    def observe(self, name: str, version: str) -> Observation:
        if (name, version) not in self.source:
            raise CacheError(f"unregistered package: {name}@{version}")
        published = self.source[(name, version)]
        slot = self.key(name, version)
        self.observe_count += 1
        if slot in self.cache:
            self.hits += 1
            payload = self.cache[slot]
            source = "stale-hit"
        else:
            self.misses += 1
            payload = published
            self.cache[slot] = payload
            source = "fill"
        return Observation(
            name=name,
            version=version,
            digest=content_digest(payload),
            payload=payload,
            source=source,
            invocations=self.observe_count,
            rebuilt=False,
        )


class AlwaysRefetchCache:
    """Both-states mutant: never hits. A 'cache' that always copies source."""

    def __init__(self) -> None:
        self.source: dict[str, tuple[str, bytes]] = {}
        self.observe_count = 0
        self.hits = 0

    def publish(self, name: str, payload: bytes, version: str) -> dict[str, Any]:
        self.source[name] = (version, payload)
        return {
            "name": name,
            "version": version,
            "digest": content_digest(payload),
            "bytes": len(payload),
        }

    def observe(self, name: str) -> Observation:
        version, payload = self.source[name]
        self.observe_count += 1
        return Observation(
            name=name,
            version=version,
            digest=content_digest(payload),
            payload=payload,
            source="refetch",
            invocations=self.observe_count,
            rebuilt=False,
        )


def measure_unchanged_served_from_cache(root: Path) -> dict[str, Any]:
    """Unchanged package is a measured cache hit (cache still works)."""
    ca = ContentAddressedPackageCache(root / "content-addressed")
    always = AlwaysRefetchCache()
    pub = ca.publish(PACKAGE, BUGGY, VERSION)
    always.publish(PACKAGE, BUGGY, VERSION)

    obs1 = ca.observe(PACKAGE)
    hits_after_first = ca.hits
    rebuilds_after_first = ca.rebuilds
    blob = ca.blob_path(obs1.digest)
    blob_bytes = blob.read_bytes() if blob.is_file() else b""
    install1 = _install(root / "install" / PACKAGE / "installed.bin", obs1.payload)

    obs2 = ca.observe(PACKAGE)
    always1 = always.observe(PACKAGE)
    always2 = always.observe(PACKAGE)

    served_from_cache = (
        obs1.source == "hit"
        and obs2.source == "hit"
        and obs1.payload == BUGGY
        and obs2.payload == BUGGY
        and obs1.digest == pub["digest"]
        and obs2.digest == pub["digest"]
        and ca.hits == hits_after_first + 1
        and ca.rebuilds == rebuilds_after_first
        and blob.is_file()
        and blob.name == obs1.digest
        and blob_bytes == BUGGY
        and install1["sha256"] == obs1.digest
    )
    always_never_hits = (
        always1.source == "refetch"
        and always2.source == "refetch"
        and always.hits == 0
    )
    both_states = served_from_cache and always_never_hits
    return {
        "unit_id": UNIT,
        "package": PACKAGE,
        "version": VERSION,
        "cache_key": obs2.digest,
        "cache_key_fn": "content_digest",
        "cache_key_equals_sha256_payload": obs2.digest == sha256_hex(BUGGY),
        "blob_path": blob.as_posix(),
        "blob_basename_is_cache_key": blob.name == obs2.digest,
        "first_source": obs1.source,
        "second_source": obs2.source,
        "hits_after_first": hits_after_first,
        "hits_after_second": ca.hits,
        "rebuilds": ca.rebuilds,
        "served_from_cache": served_from_cache,
        "always_refetch_never_hits": always_never_hits,
        "both_states": both_states,
        "install": install1,
        "pass": both_states,
    }


def measure_same_version_republish(root: Path) -> dict[str, Any]:
    """Same name+version, new bytes: CAS fetches the fix; name@version masks it."""
    ca = ContentAddressedPackageCache(root / "content-addressed")
    naive = NameVersionKeyedCache()

    pub1 = ca.publish(PACKAGE, BUGGY, VERSION)
    naive.publish(PACKAGE, BUGGY, VERSION)
    obs1 = ca.observe(PACKAGE)
    naive.observe(PACKAGE, VERSION)
    install1 = _install(root / "install-v1" / PACKAGE / "installed.bin", obs1.payload)
    key_buggy = pub1["digest"]
    blob_buggy = ca.blob_path(key_buggy)

    pub2 = ca.publish(PACKAGE, FIXED, VERSION)
    naive.publish(PACKAGE, FIXED, VERSION)
    naive_obs2 = naive.observe(PACKAGE, VERSION)
    obs2 = ca.observe(PACKAGE)
    install2 = _install(root / "install-v2" / PACKAGE / "installed.bin", obs2.payload)
    key_fixed = pub2["digest"]
    blob_fixed = ca.blob_path(key_fixed)

    nv_key = NameVersionKeyedCache.key(PACKAGE, VERSION)
    fetched_fix = (
        obs2.payload == FIXED
        and obs2.digest == key_fixed
        and key_fixed != key_buggy
        and install2["sha256"] == key_fixed
        and install2["equals_payload"]
        and blob_fixed.is_file()
        and blob_fixed.read_bytes() == FIXED
        and blob_fixed.name == key_fixed
    )
    naive_masked = naive_obs2.payload == BUGGY and naive_obs2.source == "stale-hit"
    old_blob_still_present = blob_buggy.is_file() and blob_buggy.read_bytes() == BUGGY
    versions_equal = pub1["version"] == pub2["version"] == VERSION
    return {
        "unit_id": UNIT,
        "package": PACKAGE,
        "version": VERSION,
        "versions_equal": versions_equal,
        "cache_key_fn": "content_digest",
        "cache_key_buggy": key_buggy,
        "cache_key_fixed": key_fixed,
        "keys_differ": key_buggy != key_fixed,
        "name_version_key": nv_key,
        "name_version_key_unchanged": True,
        "buggy_sha256": sha256_hex(BUGGY),
        "fixed_sha256": sha256_hex(FIXED),
        "cache_key_is_content_hash": (
            key_buggy == sha256_hex(BUGGY) and key_fixed == sha256_hex(FIXED)
        ),
        "blob_buggy": blob_buggy.as_posix(),
        "blob_fixed": blob_fixed.as_posix(),
        "old_blob_still_present": old_blob_still_present,
        "cas_fetched_fix": fetched_fix,
        "naive_still_served_stale": naive_masked,
        "install_before": install1,
        "install_after": install2,
        "observe_after_source": obs2.source,
        "observe_after_marker": obs2.marker_line(),
        "both_states": fetched_fix and naive_masked,
        "pass": fetched_fix and naive_masked and versions_equal and old_blob_still_present,
    }


def content_digest_anchor() -> dict[str, Any]:
    path = REPO / IMPL
    needle = "def content_digest(payload: bytes) -> str:"
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return {"path": IMPL, "line": i, "fn": "content_digest", "anchor": f"{IMPL}:{i}"}
    raise RuntimeError("content_digest not found")
