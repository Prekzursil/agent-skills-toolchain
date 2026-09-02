"""Install + test steps under measurement.

Three tests:
  hermetic              — truly offline (local bytes only)
  claims_offline_fetch  — comment says never downloads; actually egresses
  cache_reverify        — uses cache when present; refetches when discarded
"""
from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, Callable

from contract import EGRESS_HOST, EGRESS_PORT, LYING_COMMENT

CACHED_PAYLOAD = b"CNF-0106-CACHED-PAYLOAD-v1\n"


def touch_egress() -> dict[str, Any]:
    sock = socket.create_connection((EGRESS_HOST, EGRESS_PORT), timeout=5)
    peer = sock.getpeername()
    sock.close()
    return {"host": EGRESS_HOST, "port": EGRESS_PORT, "peer": [str(peer[0]), int(peer[1])]}


def install_from_cache_or_network(cache_file: Path) -> dict[str, Any]:
    """Install entry point: copy cache, or refetch when the cache is gone."""
    if cache_file.is_file() and cache_file.stat().st_size > 0:
        data = cache_file.read_bytes()
        return {"source": "cache", "bytes": len(data), "fetched": False}
    info = touch_egress()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(CACHED_PAYLOAD)
    return {"source": "network", "bytes": len(CACHED_PAYLOAD), "fetched": True, **info}


def test_genuinely_hermetic(cache_file: Path) -> str:
    marker = cache_file.parent / "offline.marker"
    marker.write_text("offline-ok\n", encoding="utf-8")
    got = marker.read_text(encoding="utf-8").strip()
    if got != "offline-ok":
        raise AssertionError(f"hermetic marker mismatch: {got!r}")
    return "pass"


def test_claims_offline_but_fetches(cache_file: Path) -> str:
    # LYING_COMMENT is the claim. The body still egresses. Comment is not evidence.
    _ = cache_file
    _ = LYING_COMMENT
    touch_egress()
    return "pass"


def reverify_cache_path(cache_file: Path) -> Path:
    """Separate file from install cache so a cold install cannot warm this test."""
    return cache_file.parent / "reverify.bin"


def test_cache_reverify(cache_file: Path) -> str:
    result = install_from_cache_or_network(reverify_cache_path(cache_file))
    if result["source"] == "cache" and result["fetched"]:
        raise AssertionError("cache hit marked as fetch")
    return f"pass:{result['source']}"


TESTS: list[tuple[str, Callable[[Path], str]]] = [
    ("install", lambda p: f"ok:{install_from_cache_or_network(p)['source']}"),
    ("test_genuinely_hermetic", test_genuinely_hermetic),
    ("test_claims_offline_but_fetches", test_claims_offline_but_fetches),
    ("test_cache_reverify", test_cache_reverify),
]
