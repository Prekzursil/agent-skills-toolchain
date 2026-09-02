"""Pin-aware LRU cache: pinned entries are never evicted (TST-0178).

Also the facade for the content-addressed plugin cache (IMP-0040): the on-disk
layout (``<version>/<source_sha256>/<artefact>``) is defined ONLY in
``tools/plugin-cache-reaper/reap.py``; the names below are re-exported so callers
import from the plugin package without a second implementation of the layout.
"""
from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
import threading
import time
from collections import OrderedDict
from pathlib import Path as _Path
from typing import Any


def _load_reaper():
    """Return the ``reap`` module (plugin-cache-reaper) without mutating sys.path."""
    loaded = _sys.modules.get("reap")
    if loaded is not None:
        return loaded
    path = _Path(__file__).resolve().parents[1] / "plugin-cache-reaper" / "reap.py"
    spec = _ilu.spec_from_file_location("reap", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"plugin-cache-reaper not found at {path}")
    module = _ilu.module_from_spec(spec)
    _sys.modules["reap"] = module
    spec.loader.exec_module(module)
    return module


_MOD = _load_reaper()
ContentAddressedPluginCache = _MOD.ContentAddressedPluginCache
TimeBasedPluginCache = _MOD.TimeBasedPluginCache
content_addressed_key = _MOD.content_addressed_key
cache_key = _MOD.cache_key
source_digest_of = _MOD.source_digest_of
default_produce = _MOD.default_produce


class PinnedLRUCache:
    def __init__(self, max_entries: int, max_bytes: int, pinning_enabled: bool = True) -> None:
        self.max_entries = int(max_entries)
        self.max_bytes = int(max_bytes)
        self.pinning_enabled = bool(pinning_enabled)
        self._data: OrderedDict[str, bytes] = OrderedDict()
        self._pins: dict[str, int] = {}
        self._eviction_log: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._nbytes = 0

    def pin_table(self) -> dict[str, int]:
        with self._lock:
            return {k: int(v) for k, v in self._pins.items() if v}

    def _pin_table(self) -> dict[str, int]:
        return {k: int(v) for k, v in self._pins.items() if v}

    def pin(self, key: str) -> bool:
        with self._lock:
            if key not in self._data:
                return False
            if not self.pinning_enabled:
                return False
            self._pins[key] = int(self._pins.get(key) or 0) + 1
            return True

    def unpin(self, key: str) -> None:
        with self._lock:
            cur = int(self._pins.get(key) or 0)
            if cur <= 1:
                self._pins.pop(key, None)
            else:
                self._pins[key] = cur - 1

    def get(self, key: str) -> bytes | None:
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def put(self, data: bytes, key: str | None = None) -> str:
        payload = bytes(data)
        with self._lock:
            if key is None:
                key = f"auto-{len(self._data)}"
            if key in self._data:
                self._nbytes -= len(self._data[key])
            self._data[key] = payload
            self._data.move_to_end(key)
            self._nbytes += len(payload)
            self._evict_locked()
            return key

    def _evict_locked(self) -> None:
        while self._data and (
            len(self._data) > self.max_entries or self._nbytes > self.max_bytes
        ):
            victim = None
            for cand in list(self._data.keys()):
                pins = int(self._pins.get(cand) or 0) if self.pinning_enabled else 0
                if pins > 0:
                    continue
                victim = cand
                break
            if victim is None:
                break
            table = self._pin_table()
            pins = int(self._pins.get(victim) or 0)
            body = self._data.pop(victim)
            self._nbytes -= len(body)
            self._eviction_log.append(
                {
                    "key": victim,
                    "pin_count_at_eviction": pins,
                    "pin_table_before": table,
                    "ts": time.time(),
                }
            )

    def eviction_log(self) -> list[dict[str, Any]]:
        return list(self._eviction_log)

    def stats(self) -> dict[str, Any]:
        return {
            "entries": len(self._data),
            "bytes": self._nbytes,
            "pins": dict(self._pins),
            "evictions": len(self._eviction_log),
        }
