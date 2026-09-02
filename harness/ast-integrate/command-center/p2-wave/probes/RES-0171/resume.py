"""Resume a long-running research harvest against the result cache.

Lookup is by derive_cache_key. Unchanged origin → reuse. Mutated
origin → refetch. Clock is injected (now_unix).
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from cache_key import derive_cache_key, normalize_inputs
from policy import time_bucket, ttl_seconds
from store import ResearchResultCache


def request_inputs(
    *,
    query: str,
    backend: str,
    filters: Any,
    backend_version: str,
    source_class: str,
    kind: str,
    now_unix: int,
    measured: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "query": query,
        "backend": backend,
        "filters": filters,
        "time_bucket": time_bucket(source_class, now_unix, measured),
        "backend_version": backend_version,
        "source_class": source_class,
        "kind": kind,
    }


def resume_one(
    cache: ResearchResultCache,
    request: Mapping[str, Any],
    fetcher: Callable[[], bytes],
    *,
    now_unix: int,
    origin_id: str,
    revalidate: Callable[[bytes], bytes] | None = None,
    measured: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    record = normalize_inputs(request)
    key = derive_cache_key(record)
    ttl = int(ttl_seconds(record["source_class"], measured)["ttl_seconds"])
    body, action = cache.get(
        key,
        fetcher,
        source_class=record["source_class"],
        now_unix=now_unix,
        origin_id=origin_id,
        revalidate=revalidate,
        ttl_seconds=ttl,
    )
    return {
        "key": key,
        "action": action,
        "body_bytes": len(body),
        "body": body,
        "time_bucket": record["time_bucket"],
        "ttl_seconds": ttl,
        "request": record,
    }
