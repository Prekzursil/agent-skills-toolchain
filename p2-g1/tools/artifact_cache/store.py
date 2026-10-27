"""Content-addressed cache that checksums on read and refetches on mismatch."""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

EVENT_CHECKSUM_MISMATCH = "checksum-mismatch"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class GetResult:
    payload: bytes
    digest: str
    source: str
    mismatch: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)


class IntegrityCache:
    def __init__(self, root: Path, fetch: Callable[[str], bytes]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "quarantine").mkdir(exist_ok=True)
        self.fetch = fetch
        self.stats = {
            "hits": 0,
            "misses": 0,
            "mismatches": 0,
            "quarantines": 0,
            "fetches": 0,
            "refetches": 0,
        }
        self.events: list[dict[str, Any]] = []

    def payload_path(self, key: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in key)
        d = self.root / "objects" / safe
        d.mkdir(parents=True, exist_ok=True)
        return d / "payload"

    def _meta_path(self, key: str) -> Path:
        return self.payload_path(key).with_name("meta.json")

    def _write(self, key: str, payload: bytes) -> None:
        path = self.payload_path(key)
        path.write_bytes(payload)
        meta = {"digest": sha256_bytes(payload), "bytes": len(payload)}
        self._meta_path(key).write_text(json.dumps(meta), encoding="utf-8")

    def _quarantine(self, key: str, payload: bytes, digest: str) -> None:
        qroot = self.root / "quarantine" / f"{key}-{digest[:16]}"
        qroot.mkdir(parents=True, exist_ok=True)
        (qroot / "payload").write_bytes(payload)
        (qroot / "meta.json").write_text(
            json.dumps({"key": key, "digest": digest}), encoding="utf-8"
        )
        self.stats["quarantines"] += 1

    def get(self, key: str) -> GetResult:
        path = self.payload_path(key)
        meta_path = self._meta_path(key)
        if path.is_file() and meta_path.is_file():
            data = path.read_bytes()
            live = sha256_bytes(data)
            recorded = json.loads(meta_path.read_text(encoding="utf-8")).get("digest")
            if live == recorded:
                self.stats["hits"] += 1
                return GetResult(payload=data, digest=live, source="cache", mismatch=False)
            event = {
                "type": EVENT_CHECKSUM_MISMATCH,
                "key": key,
                "on_disk": live,
                "recorded": recorded,
            }
            self.events.append(event)
            self.stats["mismatches"] += 1
            self._quarantine(key, data, live)
            fresh = self.fetch(key)
            self.stats["fetches"] += 1
            self.stats["refetches"] += 1
            self._write(key, fresh)
            return GetResult(
                payload=fresh,
                digest=sha256_bytes(fresh),
                source="fetch",
                mismatch=True,
                events=[event],
            )
        payload = self.fetch(key)
        self.stats["misses"] += 1
        self.stats["fetches"] += 1
        self._write(key, payload)
        return GetResult(payload=payload, digest=sha256_bytes(payload), source="fetch")
