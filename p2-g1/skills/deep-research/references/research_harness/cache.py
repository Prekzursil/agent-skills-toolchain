"""Query-hash cache for the deep-research harness (M-16).

Direct application of the ``content-hash-cache-pattern`` skill, with one
extension the base skill explicitly lacks: **TTL / recency awareness**. The
base pattern caches pure file content (never stale); research results DO go
stale, so each entry records ``fetched_at`` and is treated as a miss once the
per-capability TTL elapses.

Cache key = SHA-256 of a normalized ``{capability, provider, query, params}``
envelope. Each entry is one ``{hash}.json`` file (O(1) lookup, no index).
Corruption or expiry == cache miss (graceful degradation, never crash).
"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# Default on-disk cache location (overridable per call).
DEFAULT_CACHE_DIR = Path.home() / ".research-harness" / "cache"

_DAY = 24 * 3600

# Per-capability TTL in seconds. Web/news are short-lived; papers barely change.
TTL_BY_CAPABILITY: dict[str, int] = {
    "web": 1 * _DAY,
    "neural": 1 * _DAY,
    "academic": 30 * _DAY,
    "bio": 30 * _DAY,
    "code": 7 * _DAY,
    "library_docs": 7 * _DAY,
    "deep_read": 1 * _DAY,
}
DEFAULT_TTL = 1 * _DAY


@dataclass(frozen=True, slots=True)
class ResearchCacheEntry:
    """One cached provider call. ``payload`` is the raw provider result."""

    query_hash: str
    capability: str
    provider: str
    fetched_at: float
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CacheResult:
    """Outcome of a cached fetch: the payload plus whether it was a hit."""

    payload: dict[str, Any]
    hit: bool
    query_hash: str


def normalize_query(query: str) -> str:
    """Lowercase + collapse whitespace so trivially-different queries collide."""
    return " ".join(query.strip().lower().split())


def query_hash(
    capability: str,
    provider: str,
    query: str,
    params: dict[str, Any] | None = None,
) -> str:
    """SHA-256 of the normalized query envelope. Order-stable, ASCII-safe."""
    envelope = json.dumps(
        {
            "cap": capability,
            "prov": provider,
            "q": normalize_query(query),
            "p": params or {},
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(envelope.encode("utf-8")).hexdigest()


def ttl_for(capability: str) -> int:
    """TTL (seconds) for a capability, falling back to ``DEFAULT_TTL``."""
    return TTL_BY_CAPABILITY.get(capability, DEFAULT_TTL)


def _serialize(entry: ResearchCacheEntry) -> dict[str, Any]:
    return {
        "query_hash": entry.query_hash,
        "capability": entry.capability,
        "provider": entry.provider,
        "fetched_at": entry.fetched_at,
        "payload": entry.payload,
    }


def _deserialize(data: dict[str, Any]) -> ResearchCacheEntry:
    return ResearchCacheEntry(
        query_hash=data["query_hash"],
        capability=data["capability"],
        provider=data["provider"],
        fetched_at=float(data["fetched_at"]),
        payload=data["payload"],
    )


def write_cache(cache_dir: Path, entry: ResearchCacheEntry) -> None:
    """Persist an entry as ``{hash}.json`` (lazy dir creation)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{entry.query_hash}.json"
    cache_file.write_text(
        json.dumps(_serialize(entry), ensure_ascii=False),
        encoding="utf-8",
    )


def read_cache(
    cache_dir: Path,
    qhash: str,
    *,
    ttl: int,
    now: float | None = None,
) -> ResearchCacheEntry | None:
    """Return a live cached entry, or ``None`` on miss/expiry/corruption."""
    cache_file = cache_dir / f"{qhash}.json"
    if not cache_file.is_file():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        entry = _deserialize(data)
    except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError):
        return None  # corruption == miss
    current = time.time() if now is None else now
    if current - entry.fetched_at > ttl:
        return None  # expired == miss
    return entry


def fetch_with_cache(
    capability: str,
    provider: str,
    query: str,
    fetch_fn: Callable[[], dict[str, Any]],
    *,
    params: dict[str, Any] | None = None,
    cache_enabled: bool = True,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    ttl: int | None = None,
    now: float | None = None,
) -> CacheResult:
    """Service layer: cache check -> provider call -> cache write.

    ``fetch_fn`` is the (injected) zero-arg provider call; it stays pure and
    knows nothing about caching. Pass ``cache_enabled=False`` (the ``--no-cache``
    escape hatch) to force a fresh fetch for "must be current" runs.
    """
    qhash = query_hash(capability, provider, query, params)
    effective_ttl = ttl_for(capability) if ttl is None else ttl

    if cache_enabled:
        cached = read_cache(cache_dir, qhash, ttl=effective_ttl, now=now)
        if cached is not None:
            return CacheResult(payload=cached.payload, hit=True, query_hash=qhash)

    payload = fetch_fn()
    if cache_enabled:
        stamp = time.time() if now is None else now
        write_cache(
            cache_dir,
            ResearchCacheEntry(
                query_hash=qhash,
                capability=capability,
                provider=provider,
                fetched_at=stamp,
                payload=payload,
            ),
        )
    return CacheResult(payload=payload, hit=False, query_hash=qhash)
