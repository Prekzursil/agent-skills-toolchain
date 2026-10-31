"""TTL table for live-source benchmark results (TST-0303).

Per-class staleness TTLs, published verbatim in tools/bench/ttl_table.json.
A stored green from a check that queried a live external source is not a
control for today; hermetic results never expire (a stored green of a pure
function is still a measurement of the same function).
"""
from __future__ import annotations

TTL_TABLE = {
    "hermetic": None,
    "model-endpoint": 6 * 3600,
    "marketplace-index": 12 * 3600,
    "advisory-db": 24 * 3600,
    "package-registry": 24 * 3600,
    "unknown-live": 1 * 3600,
}

# Back-compat aliases for the earlier table shape.
TABLE = TTL_TABLE


def load_ttl_table() -> dict:
    return dict(TTL_TABLE)


def ttl_for(kind: str) -> int | None:
    return TTL_TABLE.get(kind)
