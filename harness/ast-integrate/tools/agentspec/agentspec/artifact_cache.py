"""Content-addressed artifact cache with bit-flip refetch (IMP-0229)."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

FAILURE_CLASSES = ("corrupted-cache", "stale-package", "invalid-key")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Counters:
    hits: int = 0
    misses: int = 0
    corrupt_refetches: int = 0
    stale_rejects: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "corrupt_refetches": self.corrupt_refetches,
            "stale_rejects": self.stale_rejects,
        }


class ArtifactCache:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.counters = Counters()

    def payload_path(self, key: str) -> Path:
        return self.root / key[:2] / key

    def get(
        self,
        key: str,
        fetcher: Callable[[], bytes],
        expected_artifact_hash: str | None = None,
    ) -> bytes:
        path = self.payload_path(key)
        if path.is_file():
            data = path.read_bytes()
            if expected_artifact_hash and sha256_hex(data) != expected_artifact_hash:
                self.counters.corrupt_refetches += 1
                data = fetcher()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                return data
            self.counters.hits += 1
            return data
        self.counters.misses += 1
        data = fetcher()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data


class IntegrityError(ValueError):
    """Fetched bytes do not match the digest they were requested under."""


class PackageCache:
    """Package lookups on top of the CAS, keyed by (inputs, package_id, digest).

    A package NAME is only a pointer. The durable name index under
    ``<root>/_names/`` remembers which digest a name last resolved to; when a
    caller asks for the same name under a NEW digest (a republished fix) the
    old pointer is counted as a ``stale_reject`` and never served -- the bytes
    are located by content, so the fix is a miss followed by a fetch, and the
    pointer moves only after the fetched bytes verify against the digest.
    """

    NAME_INDEX_DIR = "_names"

    def __init__(self, root: Path | str | ArtifactCache | None = None, inputs: dict | None = None, *args, **kwargs) -> None:
        if isinstance(root, ArtifactCache):
            self.cas = root
        else:
            self.cas = ArtifactCache(root or ".")
        self.inputs = inputs or {}

    # -- name index ------------------------------------------------------------

    def _name_index_path(self, package_id: str) -> Path:
        return self.cas.root / self.NAME_INDEX_DIR / (sha256_hex(package_id.encode("utf-8")) + ".json")

    def name_pointer(self, package_id: str) -> dict | None:
        path = self._name_index_path(package_id)
        if not path.is_file():
            return None
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return doc if isinstance(doc, dict) else None

    def _point_name(self, package_id: str, digest: str, key: str) -> None:
        path = self._name_index_path(package_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(
            json.dumps({"package_id": package_id, "digest": digest, "key": key}, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(tmp, path)

    # -- lookup ------------------------------------------------------------------

    def cache_key_for(self, package_id: str, digest: str) -> str:
        from agentspec.cache_key import derive_cache_key

        payload = dict(self.inputs)
        payload["package_id"] = package_id
        payload["input_artifact_hashes"] = [digest]
        return derive_cache_key(payload)

    def _fetch_verified(self, digest: str, fetcher: Callable[[], bytes] | None) -> bytes:
        data = fetcher() if fetcher else b""
        if sha256_hex(data) != digest:
            raise IntegrityError(
                f"fetched bytes hash to {sha256_hex(data)}, requested digest was {digest}"
            )
        return data

    def get_package(self, package_id: str, digest_or_bytes: str | bytes, fetcher=None) -> bytes:
        if isinstance(digest_or_bytes, bytes) and fetcher is None:
            current = digest_or_bytes
            digest = sha256_hex(current)

            def fetcher() -> bytes:
                return current
        else:
            digest = str(digest_or_bytes)

        key = self.cache_key_for(package_id, digest)
        pointer = self.name_pointer(package_id)
        if pointer is not None and pointer.get("digest") != digest:
            # The name still points at an older publication: stale for this
            # request. Count it and fall through to the content lookup.
            self.cas.counters.stale_rejects += 1

        path = self.cas.payload_path(key)
        if path.is_file():
            data = path.read_bytes()
            if sha256_hex(data) != digest:
                self.cas.counters.stale_rejects += 1
                data = self._fetch_verified(digest, fetcher)
                path.write_bytes(data)
                self._point_name(package_id, digest, key)
                return data
            self.cas.counters.hits += 1
            if pointer is None or pointer.get("digest") != digest:
                self._point_name(package_id, digest, key)
            return data
        self.cas.counters.misses += 1
        data = self._fetch_verified(digest, fetcher)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._point_name(package_id, digest, key)
        return data
