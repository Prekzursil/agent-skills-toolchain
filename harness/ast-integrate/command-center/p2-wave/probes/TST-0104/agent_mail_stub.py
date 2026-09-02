#!/usr/bin/env python3
"""Always-on agent-mail stand-in for TST-0104. GET /health -> 200 JSON."""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

BODY = json.dumps({"status": "ok", "service": "agent-mail", "unit": "TST-0104"}).encode(
    "utf-8"
)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/api/health", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            self.wfile.write(BODY)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> int:
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    port = int(httpd.server_address[1])
    sys.stdout.write(str(port) + "\n")
    sys.stdout.flush()
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
