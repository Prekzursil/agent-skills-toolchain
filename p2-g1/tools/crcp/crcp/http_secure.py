"""Restricted HTTP transport for CRCP's OpenAI and ChatGPT requests.

The standard urllib redirect handler can forward request headers while following
redirects.  That is unsafe for requests carrying bearer credentials.  This
module validates every destination and follows redirects explicitly, retaining
credentials only when the redirect stays on the exact same origin.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from typing import Any


ALLOWED_HOSTS = frozenset(
    {
        "chatgpt.com",
        "ab.chatgpt.com",
        "auth.openai.com",
    }
)
MAX_REDIRECTS = 5
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_CROSS_ORIGIN_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "cookie2",
        "chatgpt-account-id",
    }
)
_ENTITY_HEADERS = frozenset(
    {
        "content-length",
        "content-type",
        "content-encoding",
        "transfer-encoding",
    }
)


class URLSecurityError(ValueError):
    """Raised before I/O when an outbound URL violates the origin policy."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Return redirects to ``open_url`` instead of following implicitly."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def _validated_parts(url: str) -> urllib.parse.SplitResult:
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise URLSecurityError(f"invalid outbound URL: {exc}") from exc

    normalized_host = (host or "").lower().rstrip(".")
    if normalized_host not in ALLOWED_HOSTS:
        raise URLSecurityError("outbound host is not in the CRCP allowlist")
    if parts.scheme.lower() != "https":
        raise URLSecurityError("OpenAI and ChatGPT requests require HTTPS")
    if parts.username is not None or parts.password is not None:
        raise URLSecurityError("outbound URL must not contain user information")
    if port not in (None, 443):
        raise URLSecurityError("OpenAI and ChatGPT requests require HTTPS port 443")
    return parts


def _origin(parts: urllib.parse.SplitResult) -> tuple[str, str, int]:
    return (
        parts.scheme.lower(),
        (parts.hostname or "").lower().rstrip("."),
        parts.port or 443,
    )


def _redirect_request(
    request: urllib.request.Request,
    target: str,
    status: int,
) -> urllib.request.Request:
    old_parts = _validated_parts(request.full_url)
    new_parts = _validated_parts(target)
    same_origin = _origin(old_parts) == _origin(new_parts)

    method = request.get_method()
    data = request.data
    if status == 303 and method != "HEAD":
        method, data = "GET", None
    elif status in (301, 302) and method not in ("GET", "HEAD"):
        method, data = "GET", None

    headers: dict[str, str] = {}
    for name, value in request.header_items():
        lowered = name.lower()
        if lowered == "host":
            continue
        if not same_origin and lowered in _CROSS_ORIGIN_SENSITIVE_HEADERS:
            continue
        if data is None and lowered in _ENTITY_HEADERS:
            continue
        headers[name] = value

    return urllib.request.Request(
        target,
        data=data,
        headers=headers,
        method=method,
    )


def open_url(
    req: urllib.request.Request,
    *,
    timeout: float | None = None,
) -> Any:
    """Open an allowlisted HTTPS request with credential-safe redirects.

    Redirect destinations are resolved and validated before another connection
    is made.  Authorization and other session headers survive only same-origin
    redirects; an allowed cross-origin redirect is followed without them.
    """
    if not isinstance(req, urllib.request.Request):
        raise TypeError("open_url requires urllib.request.Request")

    _validated_parts(req.full_url)
    opener = urllib.request.build_opener(_NoRedirectHandler())
    current = req

    for redirect_count in range(MAX_REDIRECTS + 1):
        try:
            if timeout is None:
                return opener.open(current)
            return opener.open(current, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code not in _REDIRECT_CODES:
                raise
            location = exc.headers.get("Location")
            if not location:
                raise
            if redirect_count >= MAX_REDIRECTS:
                exc.close()
                raise URLSecurityError("too many HTTP redirects") from exc

            target = urllib.parse.urljoin(current.full_url, location)
            try:
                next_request = _redirect_request(current, target, exc.code)
            finally:
                exc.close()
            current = next_request

    raise AssertionError("redirect loop bound was not enforced")
