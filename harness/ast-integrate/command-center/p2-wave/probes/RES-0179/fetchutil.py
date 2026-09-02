"""Shared HTTP fetch for RES-0179 inbound reachability probes.

Records status, resolved URL, timestamp, and sha256 of the captured bytes.
Does not enable Tor, send credentials, or bypass WAF/paywall challenges.
"""
from __future__ import annotations

import hashlib
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

USER_AGENT = "RES-0179-reachability-probe/1.0 (lawful-public-research)"
DEFAULT_MAX_BYTES = 65536
SSL_CTX = ssl.create_default_context()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(
    url: str,
    *,
    timeout: float = 15.0,
    max_bytes: int = DEFAULT_MAX_BYTES,
    method: str = "GET",
) -> dict[str, Any]:
    """Fetch url. Always returns a dict; never raises for HTTP/network errors."""
    started = utc_now()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers, method=method)
    status: int | None = None
    final = url
    header_map: dict[str, str] = {}
    body = b""
    error_type = None
    error_msg = None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            status = int(getattr(resp, "status", None) or resp.getcode())
            final = resp.geturl() or url
            header_map = {k.lower(): v for k, v in resp.headers.items()}
            body = resp.read(max_bytes)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        error_type = "HTTPError"
        error_msg = str(exc.reason)[:240]
        header_map = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
        try:
            body = exc.read(max_bytes) if exc.fp else b""
        except Exception:
            body = b""
        final = url
    except Exception as exc:
        error_type = type(exc).__name__
        error_msg = str(exc)[:400]
    captured = body[:max_bytes]
    text_full = captured.decode("utf-8", "replace")
    return {
        "requested_url": url,
        "resolved_url": final,
        "fetch_timestamp": started,
        "http_status": status,
        "ok_2xx": isinstance(status, int) and 200 <= status < 300,
        "error_type": error_type,
        "error_message": error_msg,
        "content_type": header_map.get("content-type", ""),
        "server": header_map.get("server", ""),
        "waf_action": header_map.get("x-amzn-waf-action", ""),
        "cf_ray": header_map.get("cf-ray", ""),
        "bytes_captured": len(captured),
        "sha256": hashlib.sha256(captured).hexdigest() if captured else hashlib.sha256(b"").hexdigest(),
        "body_head": text_full[:800],
        "body_text": text_full,
        "redirected": final.rstrip("/") != url.rstrip("/"),
    }


def body_has(row: dict[str, Any], needle: str) -> bool:
    blob = str(row.get("body_text") or row.get("body_head") or "")
    return needle.lower() in blob.lower()


def ua_star_disallow_paths(robots_text: str) -> list[str]:
    """Return Disallow paths that apply to User-agent: *."""
    text = (robots_text or "").replace("\r\n", "\n")
    paths: list[str] = []
    for part in text.split("User-agent:"):
        lines = part.splitlines()
        if not lines:
            continue
        agent = lines[0].strip()
        if agent != "*":
            continue
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.lower().startswith("user-agent:"):
                break
            if stripped.lower().startswith("disallow:"):
                paths.append(stripped.split(":", 1)[1].strip())
    return paths
