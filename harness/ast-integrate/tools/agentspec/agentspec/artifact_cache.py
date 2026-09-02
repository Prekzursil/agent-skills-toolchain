"""Content-addressed artifact cache with bit-flip refetch (IMP-0229)."""
from __future__ import annotations

import hashlib
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


class PackageCache:
    def __init__(self, root: Path | str | ArtifactCache | None = None, inputs: dict | None = None, *args, **kwargs) -> None:
        if isinstance(root, ArtifactCache):
            self.cas = root
        else:
            self.cas = ArtifactCache(root or ".")
        self.inputs = inputs or {}

    def get_package(self, package_id: str, digest_or_bytes: str | bytes, fetcher=None) -> bytes:
        if isinstance(digest_or_bytes, bytes) and fetcher is None:
            current = digest_or_bytes
            digest = sha256_hex(current)

            def fetcher() -> bytes:
                return current
        else:
            digest = str(digest_or_bytes)
        from agentspec.cache_key import derive_cache_key

        payload = dict(self.inputs)
        payload["package_id"] = package_id
        payload["input_artifact_hashes"] = [digest]
        key = derive_cache_key(payload)
        path = self.cas.payload_path(key)
        if path.is_file():
            data = path.read_bytes()
            if sha256_hex(data) != digest:
                self.cas.counters.stale_rejects += 1
                data = fetcher() if fetcher else data
                path.write_bytes(data)
                return data
            self.cas.counters.hits += 1
            return data
        self.cas.counters.misses += 1
        data = fetcher() if fetcher else b""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data
