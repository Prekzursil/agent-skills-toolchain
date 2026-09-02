"""TTL table for live-source benchmark results."""
from __future__ import annotations

TABLE = {
    "advisory-db": 7 * 24 * 3600,
    "http-origin": 24 * 3600,
    "hermetic": None,
}


def load_ttl_table() -> dict:
    return dict(TABLE)


def ttl_for(kind: str) -> int | None:
    return TABLE.get(kind)
