#!/usr/bin/env python3
"""Live HTTP citation resolver for RES-0170.

Resolvability is HTTP status plus content match on the fetched bytes, not
the presence of a citation-shaped URL string. The server is local so the
probe is hermetic; the GET is still a real HTTP round-trip.
"""
from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

HOST = "127.0.0.1"
LOGICAL_HOST = "res-0170.test"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        routes: dict[str, dict[str, Any]] = getattr(self.server, "routes", {})
        path = urlparse(self.path).path
        route = routes.get(path)
        if route is None:
            body = b"not found\n"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        raw = route["body"]
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        status = int(route.get("status") or 200)
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if status != 204:
            self.wfile.write(raw)


class FixtureHttp:
    def __init__(self, routes: dict[str, dict[str, Any]]) -> None:
        self._httpd = ThreadingHTTPServer((HOST, 0), _Handler)
        self._httpd.routes = routes
        self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self) -> "FixtureHttp":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def __enter__(self) -> "FixtureHttp":
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    def physical_url(self, logical_url: str) -> str:
        parsed = urlparse(logical_url)
        path = parsed.path or "/"
        return f"http://{HOST}:{self.port}{path}"


def routes_from_bodies(bodies: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """bodies: path -> {status, body}."""
    out: dict[str, dict[str, Any]] = {}
    for path, spec in bodies.items():
        key = path if path.startswith("/") else "/" + path
        out[key] = {
            "status": int(spec.get("status") or 200),
            "body": spec.get("body") or "",
        }
    return out


def fetch(url: str, timeout: float = 3.0) -> dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = Request(url, method="GET", headers={"User-Agent": "RES-0170-resolver/1"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = int(resp.status)
    except HTTPError as exc:
        raw = exc.read() if exc.fp is not None else b""
        status = int(exc.code)
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "url": url,
            "http_status": None,
            "ok": False,
            "error": type(exc).__name__,
            "fetched_at": fetched_at,
            "sha256": None,
            "bytes": 0,
            "body_text": "",
        }
    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    return {
        "url": url,
        "http_status": status,
        "ok": 200 <= status < 300,
        "error": None,
        "fetched_at": fetched_at,
        "sha256": digest,
        "bytes": len(raw),
        "body_text": text,
    }


def content_match(body_text: str, claimed_quote: str) -> bool:
    quote = (claimed_quote or "").strip()
    if not quote:
        return False
    return quote in (body_text or "")


def resolve_citation(server: FixtureHttp, src: dict[str, Any]) -> dict[str, Any]:
    logical = str(src.get("url") or "")
    physical = server.physical_url(logical)
    got = fetch(physical)
    quote = str(src.get("claimed_quote") or "")
    matched = bool(got.get("ok")) and content_match(str(got.get("body_text") or ""), quote)
    return {
        **src,
        "logical_url": logical,
        "resolved_url": physical,
        "http_status": got["http_status"],
        "fetched_at": got["fetched_at"],
        "sha256": got["sha256"],
        "fetch_bytes": got["bytes"],
        "fetch_ok": bool(got.get("ok")),
        "content_match": matched,
        "resolvable": bool(got.get("ok")) and matched,
        "fetch_error": got.get("error"),
    }
