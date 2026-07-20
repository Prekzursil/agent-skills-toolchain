"""Recursive, metadata-safe redaction for CRCP reports and logs."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


REDACTED = "[REDACTED]"
_SECRET_KEY = re.compile(
    r"(?:authorization|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"bearer|jwt|secret|password|proof[_-]?token|prepare[_-]?token|"
    r"turnstile[_-]?token|conduit[_-]?token|resume[_-]?token)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_JWT = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


def _redact_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.scheme or not parts.netloc or not parts.query:
        return value
    query = [
        (key, REDACTED if _SECRET_KEY.search(key) else item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def redact(value: Any) -> Any:
    """Return a deep redacted copy without mutating the input value."""
    if isinstance(value, dict):
        return {
            key: REDACTED if _SECRET_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        cleaned = _BEARER.sub(f"Bearer {REDACTED}", value)
        cleaned = _JWT.sub(REDACTED, cleaned)
        return _redact_url(cleaned)
    return value
