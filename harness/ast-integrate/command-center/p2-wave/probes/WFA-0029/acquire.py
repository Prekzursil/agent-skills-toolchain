"""Choke point for every credentialed external acquisition call and its retries.

Sweep-lane code must call credentialed_call (or credentialed_get). Live I/O is
injected as a transport; this module never opens a socket on its own, so a dry
run cannot accidentally hit a provider. Retries (429/5xx) re-enter admit().
Non-transient 4xx is not retried.
"""
from __future__ import annotations

from typing import Any, Callable

from scheduler import Scheduler

RETRYABLE = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3

Transport = Callable[[dict[str, Any]], dict[str, Any]]


def _status_of(resp: Any) -> int:
    if isinstance(resp, dict):
        return int(resp.get("status") or resp.get("status_code") or 0)
    return int(getattr(resp, "status", 0) or getattr(resp, "status_code", 0) or 0)


def credentialed_call(
    provider: str,
    transport: Transport,
    request: dict[str, Any] | None = None,
    scheduler: Scheduler | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> dict[str, Any]:
    """Admit, invoke transport, retry transient failures through admit again."""
    if scheduler is None:
        raise TypeError("credentialed_call requires an explicit Scheduler")
    if not callable(transport):
        raise TypeError("transport must be callable")
    req = dict(request or {})
    req.setdefault("provider", provider)
    last: dict[str, Any] | None = None
    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        with scheduler.admit(provider) as adm:
            raw = transport(req)
        if not isinstance(raw, dict):
            raw = {"status": _status_of(raw), "body": raw}
        raw = dict(raw)
        raw["admitted_at"] = adm.admitted_at
        raw["waited_seconds"] = adm.waited_seconds
        raw["attempt"] = attempts
        last = raw
        status = _status_of(raw)
        if status == 429 or status in RETRYABLE:
            if attempts >= max_attempts:
                break
            backoff = 2 ** (attempts - 1)
            scheduler.clock.sleep(float(backoff))
            continue
        if 400 <= status < 500:
            break
        break
    assert last is not None
    last["attempts"] = attempts
    return last


def credentialed_get(
    provider: str,
    url: str,
    transport: Transport,
    scheduler: Scheduler | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    return credentialed_call(
        provider,
        transport,
        request={"method": "GET", "url": url, "headers": dict(headers or {})},
        scheduler=scheduler,
    )
