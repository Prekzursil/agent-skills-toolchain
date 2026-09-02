"""Local intercepting HTTP sink-proxy for ADV-0039 probe 2."""
from __future__ import annotations

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


def collect_keys(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.add(str(key))
            keys |= collect_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            keys |= collect_keys(item)
    return keys


def capture_posts(payloads: list[Any], dest: str = "http://telemetry.invalid/v1/ingest") -> list[dict[str, Any]]:
    """POST each payload through a localhost HTTP proxy that records JSON keys.

    The proxy is a sink: it does not forward off-box. urllib still issues a
    real HTTP POST in absolute-form, so keys are observed after serialization.
    """
    captured: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            parsed: Any = None
            keys: list[str] = []
            try:
                parsed = json.loads(body.decode("utf-8"))
                keys = sorted(collect_keys(parsed))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None
            captured.append(
                {
                    "path": self.path,
                    "host": self.headers.get("Host"),
                    "bytes": length,
                    "keys": keys,
                }
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    proxy_url = f"http://127.0.0.1:{port}"
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy_url})
    )
    try:
        for payload in payloads:
            data = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            req = urllib.request.Request(
                dest,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with opener.open(req, timeout=5) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"proxy POST status {resp.status}")
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    if len(captured) != len(payloads):
        raise RuntimeError(
            f"proxy captured {len(captured)} posts, expected {len(payloads)}"
        )
    return captured
