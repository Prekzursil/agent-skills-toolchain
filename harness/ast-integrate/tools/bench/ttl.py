"""TTL table for live-source benchmark results (TST-0303).

The table lives in ``tools/bench/ttl_table.json`` so the per-class staleness
budget is data, not code. ``null`` means the class never expires (hermetic).
An unknown class is treated as live with the ``unknown-live`` budget rather
than as never-expiring.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

TABLE_PATH = Path(__file__).resolve().with_name("ttl_table.json")

_FALLBACK = {
    "hermetic": None,
    "advisory-db": 7 * 24 * 3600,
    "marketplace-index": 24 * 3600,
    "model-endpoint": 24 * 3600,
    "package-registry": 24 * 3600,
    "http-origin": 24 * 3600,
    "unknown-live": 3600,
}


@lru_cache(maxsize=1)
def _load() -> dict[str, int | None]:
    if TABLE_PATH.is_file():
        doc = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
        raw = doc.get("ttl_seconds") if isinstance(doc, dict) else None
        if isinstance(raw, dict):
            return {str(k): (None if v is None else int(v)) for k, v in raw.items()}
    return dict(_FALLBACK)


def load_ttl_table() -> dict[str, int | None]:
    return dict(_load())


def ttl_for(kind: str) -> int | None:
    """Seconds before a result of this class goes stale; None = never."""
    table = _load()
    key = str(kind or "")
    if key in table:
        return table[key]
    if key == "":
        return table.get("unknown-live", 3600)
    return table.get("unknown-live", 3600)


TABLE = _load()
