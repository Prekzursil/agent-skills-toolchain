"""Development-loop cache with --no-cache bypass and LRU retention (IMP-0042)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


def _now_ns() -> int:
    return int(os.times_result(os.times()).elapsed * 1e9) if False else _clock_ns()


_CLOCK: Callable[[], int] | None = None


def _clock_ns() -> int:
    if _CLOCK is not None:
        return int(_CLOCK())
    return int(os.time_ns())


@dataclass
class Counters:
    hits: int = 0
    misses: int = 0
    recomputes: int = 0
    evictions: int = 0


@dataclass
class DevCache:
    """Content cache keyed by (name, source-digest, version)."""

    root: Path
    max_entries: int = 32
    max_bytes: int = 1_000_000
    retention_floor: int = 1
    clock: Callable[[], int] | None = None
    counters: Counters = field(default_factory=Counters)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "index.json"
        if not self._index_path.is_file():
            self._write_index([])

    def _read_index(self) -> list[dict[str, Any]]:
        try:
            rows = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return rows if isinstance(rows, list) else []

    def _write_index(self, rows: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path.write_text(
            json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def _tick(self) -> int:
        if self.clock is not None:
            return int(self.clock())
        return int(os.time_ns())

    def _entry_path(self, key: str) -> Path:
        return self.root / "blobs" / key

    def get_or_compute(
        self,
        name: str,
        source: bytes,
        version: str,
        compute_fn: Callable[[bytes], bytes],
        *,
        no_cache: bool = False,
    ) -> bytes:
        digest = hashlib.sha256(source).hexdigest()
        key = hashlib.sha256(f"{name}\0{version}\0{digest}".encode("utf-8")).hexdigest()
        path = self._entry_path(key)
        if no_cache:
            self.counters.recomputes += 1
            return compute_fn(source)
        if path.is_file():
            self.counters.hits += 1
            rows = self._read_index()
            for row in rows:
                if row.get("key") == key:
                    row["last_access_ns"] = self._tick()
            self._write_index(rows)
            return path.read_bytes()
        payload = compute_fn(source)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        rows = self._read_index()
        rows.append(
            {
                "name": name,
                "key": key,
                "version": version,
                "bytes": len(payload),
                "last_access_ns": self._tick(),
            }
        )
        self.counters.misses += 1
        self._write_index(rows)
        apply_retention(
            self.root,
            max_entries=self.max_entries,
            max_bytes=self.max_bytes,
            retention_floor=self.retention_floor,
            counters=self.counters,
        )
        return payload


def apply_retention(
    root: Path,
    *,
    max_entries: int = 32,
    max_bytes: int = 1_000_000,
    retention_floor: int = 1,
    counters: Counters | None = None,
) -> list[dict[str, Any]]:
    """Evict oldest entries until under both ceilings; keep retention_floor newest."""
    root = Path(root)
    index_path = root / "index.json"
    try:
        rows = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(rows, list):
        return []
    rows = sorted(rows, key=lambda r: int(r.get("last_access_ns") or 0))
    floor = max(int(retention_floor), 0)

    def _over() -> bool:
        n = len(rows)
        b = sum(int(r.get("bytes") or 0) for r in rows)
        return n > max_entries or b > max_bytes

    while _over() and len(rows) > floor:
        victim = rows.pop(0)
        blob = root / "blobs" / str(victim.get("key") or "")
        try:
            blob.unlink()
        except OSError:
            pass
        if counters is not None:
            counters.evictions += 1
    index_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rows


def list_entries(root: Path) -> list[dict[str, Any]]:
    root = Path(root)
    index_path = root / "index.json"
    try:
        rows = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return list(rows) if isinstance(rows, list) else []


def flag_no_cache(argv: list[str] | None = None) -> bool:
    argv = list(argv or [])
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--cache-dir")
    parser.add_argument("--name")
    parser.add_argument("--max-entries", type=int, default=32)
    parser.add_argument("--max-bytes", type=int, default=1_000_000)
    ns, _unknown = parser.parse_known_args(argv)
    return bool(ns.no_cache)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cache_policy")
    parser.add_argument("--no-cache", action="store_true", help="recompute; write nothing")
    parser.add_argument("--cache-dir", required=False)
    parser.add_argument("--name", required=False)
    parser.add_argument("--max-entries", type=int, default=32)
    parser.add_argument("--max-bytes", type=int, default=1_000_000)
    parser.add_argument("--retention-floor", type=int, default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    print(json.dumps({"no_cache": bool(ns.no_cache), "cache_dir": ns.cache_dir}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
