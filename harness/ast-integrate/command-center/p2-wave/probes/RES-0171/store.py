"""On-disk research result cache with integrity on read.

A truncated, empty, or hash-mismatched entry is never served. The
fetcher is invoked and the entry is replaced (corrupted-cache path).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from cache_key import sha256_bytes

SCHEMA_ID = "res-0171-research-cache-entry-v1"


class CorruptedCacheEntry(ValueError):
    pass


@dataclass
class Counters:
    misses: int = 0
    hits: int = 0
    revalidations: int = 0
    refetches: int = 0
    corrupt_refetches: int = 0
    reuse_unchanged: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "misses": self.misses,
            "hits": self.hits,
            "revalidations": self.revalidations,
            "refetches": self.refetches,
            "corrupt_refetches": self.corrupt_refetches,
            "reuse_unchanged": self.reuse_unchanged,
        }


@dataclass
class ResearchResultCache:
    root: Path
    counters: Counters = field(default_factory=Counters)

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def entry_path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def payload_path(self, key: str) -> Path:
        return self.root / f"{key}.body"

    def _read_entry(self, key: str) -> dict[str, Any]:
        meta_path = self.entry_path(key)
        body_path = self.payload_path(key)
        if not meta_path.is_file() or not body_path.is_file():
            raise FileNotFoundError(key)
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CorruptedCacheEntry(f"meta-unparseable:{type(exc).__name__}") from exc
        if not isinstance(meta, dict) or meta.get("schema_id") != SCHEMA_ID:
            raise CorruptedCacheEntry("wrong-schema")
        body = body_path.read_bytes()
        if not body:
            raise CorruptedCacheEntry("zero-byte-body")
        if sha256_bytes(body) != str(meta.get("body_sha256") or ""):
            raise CorruptedCacheEntry("body-hash-mismatch")
        if int(meta.get("body_bytes") or -1) != len(body):
            raise CorruptedCacheEntry("body-bytes-mismatch")
        meta["_body"] = body
        return meta

    def put(
        self,
        key: str,
        body: bytes,
        *,
        source_class: str,
        fetched_at: int,
        origin_id: str,
    ) -> dict[str, Any]:
        if not body:
            raise ValueError("refuse empty body")
        digest = sha256_bytes(body)
        meta = {
            "schema_id": SCHEMA_ID,
            "key": key,
            "source_class": source_class,
            "fetched_at": int(fetched_at),
            "origin_id": origin_id,
            "body_sha256": digest,
            "body_bytes": len(body),
        }
        self.payload_path(key).write_bytes(body)
        self.entry_path(key).write_text(
            json.dumps(meta, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return meta

    def get(
        self,
        key: str,
        fetcher: Callable[[], bytes],
        *,
        source_class: str,
        now_unix: int,
        origin_id: str,
        revalidate: Callable[[bytes], bytes] | None = None,
        ttl_seconds: int = 0,
    ) -> tuple[bytes, str]:
        """Return (body, action) where action is miss|reuse|refetch|corrupt-refetch.

        revalidate(stored) -> current origin bytes. When ttl_seconds==0
        (must-revalidate), origin is always consulted. When origin bytes
        match stored, the stored body is reused (action=reuse). When they
        differ, the new body is stored (action=refetch).
        """
        try:
            meta = self._read_entry(key)
        except FileNotFoundError:
            body = fetcher()
            self.put(
                key,
                body,
                source_class=source_class,
                fetched_at=now_unix,
                origin_id=origin_id,
            )
            self.counters.misses += 1
            return body, "miss"
        except CorruptedCacheEntry:
            body = fetcher()
            self.put(
                key,
                body,
                source_class=source_class,
                fetched_at=now_unix,
                origin_id=origin_id,
            )
            self.counters.corrupt_refetches += 1
            self.counters.refetches += 1
            return body, "corrupt-refetch"

        stored: bytes = meta["_body"]
        age = now_unix - int(meta.get("fetched_at") or 0)
        must_revalidate = ttl_seconds <= 0 or age >= ttl_seconds
        if not must_revalidate:
            self.counters.hits += 1
            self.counters.reuse_unchanged += 1
            return stored, "reuse"

        self.counters.revalidations += 1
        if revalidate is None:
            current = fetcher()
        else:
            current = revalidate(stored)
        if sha256_bytes(current) == sha256_bytes(stored):
            self.put(
                key,
                stored,
                source_class=source_class,
                fetched_at=now_unix,
                origin_id=origin_id,
            )
            self.counters.hits += 1
            self.counters.reuse_unchanged += 1
            return stored, "reuse"
        self.put(
            key,
            current,
            source_class=source_class,
            fetched_at=now_unix,
            origin_id=origin_id,
        )
        self.counters.refetches += 1
        return current, "refetch"
