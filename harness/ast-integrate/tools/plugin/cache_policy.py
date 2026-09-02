"""Development-loop cache with --no-cache bypass and LRU retention (IMP-0042)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


def _now_ns() -> int:
    """Monotonic-enough wall clock in ns (overridable through ``_CLOCK`` for tests)."""
    return _clock_ns()


_CLOCK: Callable[[], int] | None = None


def _clock_ns() -> int:
    if _CLOCK is not None:
        return int(_CLOCK())
    return int(time.time_ns())


@dataclass
class Counters:
    hits: int = 0
    misses: int = 0
    recomputes: int = 0
    evictions: int = 0


DEFAULT_MAX_ENTRIES = 32
DEFAULT_MAX_BYTES = 1_000_000
DEFAULT_RETENTION_FLOOR = 1


def default_dev_cache_root() -> Path:
    """Where the development-loop cache lives when nobody passes ``--cache-dir``.

    A sibling of the vendor plugin cache (``~/.claude/plugins/cache``) rather than a
    child of it: the staging reaper scans that directory non-recursively by NAME, and
    keeping our own cache next to it -- not inside it -- means one scheduled task can
    bound both without either ever becoming a candidate of the other.
    """
    override = os.environ.get("AST_PLUGIN_DEV_CACHE")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "plugins" / "dev-cache"


@dataclass
class DevCache:
    """Content cache keyed by (name, source-digest, version)."""

    root: Path
    max_entries: int = DEFAULT_MAX_ENTRIES
    max_bytes: int = DEFAULT_MAX_BYTES
    retention_floor: int = DEFAULT_RETENTION_FLOOR
    clock: Callable[[], int] | None = None
    counters: Counters = field(default_factory=Counters)
    idle_ttl_ns: int | None = None

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
        return int(time.time_ns())

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
            idle_ttl_ns=self.idle_ttl_ns,
            now_ns=self._tick(),
        )
        return payload


def _load_index(root: Path) -> list[dict[str, Any]] | None:
    """The index rows, or ``None`` when there is no readable index (nothing to retain)."""
    try:
        rows = json.loads((Path(root) / "index.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return rows if isinstance(rows, list) else None


def retention_plan(
    root: Path,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_bytes: int = DEFAULT_MAX_BYTES,
    retention_floor: int = DEFAULT_RETENTION_FLOOR,
    idle_ttl_ns: int | None = None,
    now_ns: int | None = None,
) -> dict[str, Any]:
    """Decide -- without touching disk -- which entries retention would evict.

    This is THE retention decision; ``apply_retention`` executes exactly this plan and
    the reaper's scheduled task consumes it too, so there is one control plane.  Order:
    idle-TTL victims first (an entry not touched for ``idle_ttl_ns`` is stale however
    small), then LRU eviction until both the entry and byte ceilings hold.  Never
    evicts below ``retention_floor`` newest entries -- a floor beats every ceiling.
    """
    rows = _load_index(root)
    if rows is None:
        return {
            "root": str(root),
            "index_present": False,
            "victims": [],
            "kept": [],
            "bytes_before": 0,
            "bytes_after": 0,
        }
    rows = sorted(rows, key=lambda r: int(r.get("last_access_ns") or 0))
    floor = max(int(retention_floor), 0)
    bytes_before = sum(int(r.get("bytes") or 0) for r in rows)
    victims: list[dict[str, Any]] = []

    if idle_ttl_ns is not None and idle_ttl_ns >= 0:
        now = int(now_ns) if now_ns is not None else _now_ns()
        fresh: list[dict[str, Any]] = []
        for row in rows:
            idle = now - int(row.get("last_access_ns") or 0)
            # Oldest first, so the floor protects the NEWEST entries.
            if idle > int(idle_ttl_ns) and (len(rows) - len(victims)) > floor:
                victims.append({**row, "reason": "idle-ttl"})
            else:
                fresh.append(row)
        rows = fresh

    def _over() -> bool:
        return len(rows) > max_entries or sum(int(r.get("bytes") or 0) for r in rows) > max_bytes

    while _over() and len(rows) > floor:
        victims.append({**rows.pop(0), "reason": "over-ceiling"})

    return {
        "root": str(root),
        "index_present": True,
        "victims": victims,
        "kept": rows,
        "bytes_before": bytes_before,
        "bytes_after": sum(int(r.get("bytes") or 0) for r in rows),
    }


def apply_retention(
    root: Path,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_bytes: int = DEFAULT_MAX_BYTES,
    retention_floor: int = DEFAULT_RETENTION_FLOOR,
    counters: Counters | None = None,
    idle_ttl_ns: int | None = None,
    now_ns: int | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Evict oldest entries until under both ceilings; keep retention_floor newest.

    Executes ``retention_plan``; with ``dry_run`` nothing on disk changes and the
    surviving rows are merely reported.  Returns the rows that remain (or would).
    """
    root = Path(root)
    plan = retention_plan(
        root,
        max_entries=max_entries,
        max_bytes=max_bytes,
        retention_floor=retention_floor,
        idle_ttl_ns=idle_ttl_ns,
        now_ns=now_ns,
    )
    if not plan["index_present"]:
        return []
    rows: list[dict[str, Any]] = plan["kept"]
    if dry_run:
        return rows
    for victim in plan["victims"]:
        blob = root / "blobs" / str(victim.get("key") or "")
        try:
            blob.unlink()
        except OSError:
            pass
        if counters is not None:
            counters.evictions += 1
    (root / "index.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
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
    parser.add_argument("--max-entries", type=int, default=DEFAULT_MAX_ENTRIES)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--retention-floor", type=int, default=DEFAULT_RETENTION_FLOOR)
    parser.add_argument(
        "--idle-ttl-seconds",
        type=float,
        default=None,
        help="also evict entries idle longer than this (floor still wins)",
    )
    parser.add_argument(
        "--apply", action="store_true", help="execute the retention plan (default: report only)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    report: dict[str, Any] = {"no_cache": bool(ns.no_cache), "cache_dir": ns.cache_dir}
    if ns.cache_dir:
        ttl_ns = int(ns.idle_ttl_seconds * 1e9) if ns.idle_ttl_seconds is not None else None
        plan = retention_plan(
            Path(ns.cache_dir),
            max_entries=ns.max_entries,
            max_bytes=ns.max_bytes,
            retention_floor=ns.retention_floor,
            idle_ttl_ns=ttl_ns,
        )
        if ns.apply:
            apply_retention(
                Path(ns.cache_dir),
                max_entries=ns.max_entries,
                max_bytes=ns.max_bytes,
                retention_floor=ns.retention_floor,
                idle_ttl_ns=ttl_ns,
            )
        report["retention"] = {
            "applied": bool(ns.apply),
            "index_present": plan["index_present"],
            "victims": [str(v.get("name")) for v in plan["victims"]],
            "kept": len(plan["kept"]),
            "bytes_before": plan["bytes_before"],
            "bytes_after": plan["bytes_after"],
        }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
