#!/usr/bin/env python3
"""A tiny stdlib fake of the TrailSearch HTTP API for search-hub adapter tests.

TrailSearch (github ``jianjungki/tavily-open``) is an external service; this fake
stands in for it so the self-hosted adapter can be exercised over a REAL loopback
socket with NO Docker, NO SearXNG, and NO network. It answers the two Tavily
routes the adapter fronts plus a health route, and can simulate the failure modes
the adapter must degrade on:

* ``GET  /docs``            -> 200 (healthy) so ``probe()`` reports reachable.
* ``POST /tavily/search``   -> a Tavily-shaped payload echoing the query.
* ``POST /tavily/extract``  -> a Tavily-shaped extract payload echoing the URLs.
* a body containing ``"boom"`` (query or first URL) -> HTTP 500 (backend error).

Used two ways: (1) as a ``fake_caller`` importable in pure unit tests, and (2) as
a runnable server (``python fake_trailsearch_backend.py [port]``) for an
integration test and the compose smoke check.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


def build_search_response(body: dict) -> dict:
    """The Tavily-shaped ``/tavily/search`` payload the adapter expects."""
    query = body.get("query", "")
    return {
        "query": query,
        "answer": ("stub answer" if body.get("include_answer") else None),
        "results": [
            {
                "title": f"result for {query}",
                "url": "https://example.test/1",
                "content": f"content about {query}",
                "score": 0.99,
                "source_stage": "searxng",
            }
        ],
        "failed_results": [],
        "response_time": 0.012,
        "timings_ms": {"search_total": 12.0},
    }


def build_extract_response(body: dict) -> dict:
    """The Tavily-shaped ``/tavily/extract`` payload the adapter expects."""
    urls = body.get("urls", []) or []
    return {
        "query": body.get("query", ""),
        "results": [
            {"url": url, "content": f"extracted {url}", "score": 0.5} for url in urls
        ],
        "failed_results": [],
        "response_time": 0.02,
    }


def route(method: str, path: str, body: dict) -> tuple[int, dict | None]:
    """Pure request router shared by the socket server and the ``fake_caller``."""
    if method == "GET" and path == "/docs":
        return 200, {"ok": True}
    if method == "POST" and path == "/tavily/search":
        if "boom" in str(body.get("query", "")):
            return 500, {"detail": "simulated backend failure"}
        return 200, build_search_response(body)
    if method == "POST" and path == "/tavily/extract":
        if any("boom" in str(u) for u in (body.get("urls") or [])):
            return 500, {"detail": "simulated backend failure"}
        return 200, build_extract_response(body)
    return 404, {"detail": "not found"}


def fake_caller(
    method: str, url: str, body: bytes | None, headers: dict, timeout: float
) -> tuple[int, dict | None, str]:
    """A stdlib-only ``adapters.Caller`` that never touches the network."""
    path = url.split("://", 1)[-1]
    path = path[path.find("/") :] if "/" in path else "/"
    parsed = json.loads(body.decode("utf-8")) if body else {}
    status, payload = route(method, path, parsed)
    raw = json.dumps(payload) if payload is not None else ""
    return status, payload, raw


class _Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict | None) -> None:
        raw = json.dumps(payload or {}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        status, payload = route("GET", self.path, {})
        self._send(status, payload)

    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, ValueError):
            parsed = {}
        status, payload = route("POST", self.path, parsed)
        self._send(status, payload)

    def log_message(self, *_args) -> None:  # keep the test output quiet
        return


def main(argv: list[str]) -> int:
    port = int(argv[0]) if argv else 0
    server = HTTPServer(("127.0.0.1", port), _Handler)
    print(f"fake-trailsearch listening on http://127.0.0.1:{server.server_address[1]}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
