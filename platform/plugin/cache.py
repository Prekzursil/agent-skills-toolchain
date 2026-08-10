"""Content-addressed cache with refresh, invalidation, and corrupted-entry quarantine.

The key is the source blob's EOL-normalised sha256 (IMP-0040), so a CRLF checkout and an LF
checkout of the same file share one entry instead of thrashing. Three properties:

* **Self-verifying.** An entry whose bytes do not hash to its own key is corrupt by construction;
  ``verify`` finds it without any external manifest.
* **Fail-open (IMP-0041).** A corrupt entry is quarantined and the caller continues from source.
  A cache is an accelerator; a broken accelerator must not become an outage. This is the one
  ``fail-open`` row in the error taxonomy and it is declared there explicitly.
* **Bounded.** ``prune`` enforces a byte ceiling by evicting least-recently-used entries, so the
  cache cannot silently grow into the "gigabytes of unrelated content" the spec forbids.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .fsops import atomic_write_bytes, dir_size, hash_bytes, iter_files, rmtree

QUARANTINE = "quarantine"
DEFAULT_MAX_BYTES = 256 * 1024 * 1024


@dataclass
class CacheStats:
    entries: int
    bytes: int
    quarantined: int
    evicted: int = 0
    bypassed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact": "cache-status",
            "entries": self.entries,
            "bytes": self.bytes,
            "quarantined": self.quarantined,
            "evicted": self.evicted,
            "bypass_active": self.bypassed,
        }


class Cache:
    """Content-addressed store rooted at ``<prefix>/state/cache``."""

    def __init__(
        self, root: Path, *, max_bytes: int = DEFAULT_MAX_BYTES, bypass: bool = False
    ) -> None:
        self.root = root
        self.max_bytes = max_bytes
        self.bypass = bypass
        self.quarantine = root / QUARANTINE

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / key

    def put(self, data: bytes) -> str:
        key = hash_bytes(data)
        if self.bypass:
            return key
        atomic_write_bytes(self._path(key), data)
        return key

    def get(self, key: str) -> bytes | None:
        """Return the entry, or None on miss / corruption. A corrupt entry is quarantined."""
        if self.bypass:
            return None
        p = self._path(key)
        if not p.exists():
            return None
        data = p.read_bytes()
        if hash_bytes(data) != key:
            self._quarantine(p, key, "content does not hash to its key")
            return None
        p.touch()
        return data

    def _quarantine(self, path: Path, key: str, reason: str) -> None:
        dest = self.quarantine / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(dest, path.read_bytes())
        atomic_write_bytes(
            dest.with_suffix(".reason.json"),
            (
                json.dumps(
                    {"key": key, "reason": reason, "at": round(time.time(), 3)},
                    sort_keys=True,
                )
                + "\n"
            ).encode(),
        )
        path.unlink()

    def verify(self) -> list[str]:
        """Quarantine every self-inconsistent entry. Returns the quarantined keys."""
        bad: list[str] = []
        for f in list(iter_files(self.root)):
            if self.quarantine in f.parents:
                continue
            key = f.name
            if hash_bytes(f.read_bytes()) != key:
                self._quarantine(f, key, "content does not hash to its key")
                bad.append(key)
        return bad

    def invalidate(self, key: str | None = None) -> int:
        """Drop one entry, or the whole cache (never the quarantine, which is evidence)."""
        if key:
            p = self._path(key)
            if p.exists():
                p.unlink()
                return 1
            return 0
        removed = 0
        for f in list(iter_files(self.root)):
            if self.quarantine in f.parents:
                continue
            f.unlink()
            removed += 1
        return removed

    def refresh(self, sources: dict[str, bytes]) -> dict[str, str]:
        """Re-key the given sources; a changed source produces a new key, so staleness is impossible."""
        return {rel: self.put(blob) for rel, blob in sorted(sources.items())}

    def prune(self) -> int:
        """LRU eviction down to the byte ceiling."""
        total, _ = dir_size(self.root)
        if total <= self.max_bytes:
            return 0
        files = sorted(
            (f for f in iter_files(self.root) if self.quarantine not in f.parents),
            key=lambda f: f.stat().st_mtime,
        )
        evicted = 0
        for f in files:
            if total <= self.max_bytes:
                break
            total -= f.stat().st_size
            f.unlink()
            evicted += 1
        return evicted

    def stats(self) -> CacheStats:
        total, count = dir_size(self.root)
        qcount = (
            sum(1 for _ in iter_files(self.quarantine))
            if self.quarantine.exists()
            else 0
        )
        return CacheStats(
            entries=count - qcount,
            bytes=total,
            quarantined=qcount,
            bypassed=self.bypass,
        )

    def purge_quarantine(self) -> None:
        rmtree(self.quarantine)
