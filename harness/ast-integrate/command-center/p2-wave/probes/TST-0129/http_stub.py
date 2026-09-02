"""Local marketplace registry HTTP stub serving application/json."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from install import LIVE_INDEX


class _Handler(BaseHTTPRequestHandler):
    body = json.dumps(LIVE_INDEX, separators=(",", ":")).encode("utf-8")

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.json"):
            payload = self.body
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_error(404)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


class RegistryHttp:
    def __init__(self) -> None:
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.ip, self.port = self._httpd.server_address
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=1.0)

    def __enter__(self) -> "RegistryHttp":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
