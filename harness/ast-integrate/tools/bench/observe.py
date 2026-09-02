"""Network observer for live-source detection (TST-0303).

``NetworkObserver`` is a context manager that intercepts ``urllib.request.urlopen``
while active, records every attempted call (URL, host, scheme, method) and answers
it from a small in-memory stub instead of touching the wire. The observed class of
a benchmark case is derived from these recorded hosts, never from what the case
declares about itself.
"""
from __future__ import annotations

import io
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


def _split_url(url: Any) -> tuple[str, str, str]:
    """Return (url, host, scheme) for a str or Request-like object."""
    if hasattr(url, "full_url"):
        url = url.full_url
    text = str(url or "")
    parts = urlsplit(text)
    host = (parts.hostname or "").lower().rstrip(".")
    return text, host, parts.scheme.lower()


def is_loopback_host(host: str) -> bool:
    h = str(host or "").strip().lower().rstrip(".")
    return h in LOOPBACK_HOSTS or h.startswith("127.") or h.endswith(".localhost")


class _StubResponse(io.BytesIO):
    """Minimal urlopen-compatible response served instead of a live fetch."""

    status = 200
    reason = "OK"

    def __init__(self, url: str) -> None:
        super().__init__(b"{}")
        self.url = url
        self.headers: dict[str, str] = {"Content-Type": "application/json"}

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self.url

    def info(self) -> dict[str, str]:
        return self.headers

    def __enter__(self) -> "_StubResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


@dataclass
class NetworkObserver:
    """Record every urlopen attempted while the observer is active."""

    calls: list[dict[str, Any]] = field(default_factory=list)
    _original: Any = field(default=None, repr=False)
    _depth: int = field(default=0, repr=False)

    def record(self, url: Any, **kwargs: Any) -> dict[str, Any]:
        text, host, scheme = _split_url(url)
        row = {"url": text, "host": host, "scheme": scheme, "loopback": is_loopback_host(host)}
        row.update(kwargs)
        self.calls.append(row)
        return row

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self.calls)

    def hosts(self) -> list[str]:
        seen: list[str] = []
        for call in self.calls:
            host = str(call.get("host") or "")
            if host and not is_loopback_host(host) and host not in seen:
                seen.append(host)
        return seen

    def _intercept(self, url: Any, data: Any = None, timeout: Any = None, *args: Any, **kwargs: Any):
        method = "POST" if data is not None else "GET"
        if hasattr(url, "get_method"):
            try:
                method = str(url.get_method())
            except Exception:  # pragma: no cover - defensive
                pass
        row = self.record(url, method=method)
        return _StubResponse(row["url"])

    def __enter__(self) -> "NetworkObserver":
        if self._depth == 0:
            self._original = urllib.request.urlopen
            urllib.request.urlopen = self._intercept  # type: ignore[assignment]
        self._depth += 1
        return self

    def __exit__(self, *exc: object) -> None:
        self._depth -= 1
        if self._depth == 0 and self._original is not None:
            urllib.request.urlopen = self._original  # type: ignore[assignment]
            self._original = None
