"""Local HTTPS fixture servers plus a plaintext HTTP trap."""
from __future__ import annotations

import ssl
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any

from certs import FixtureCerts

INDEX_BODY = b'{"registry":"tst-0130-live","packages":["fixture.pkg"],"nonce":"valid-leaf"}\n'
PACKAGE_BODY = b"TST-0130-PACKAGE-BLOB\n"
TRAP_BODY = b"plaintext-should-never-be-read\n"


class _Threaded(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _handler(body: bytes, hits: list[dict[str, Any]], label: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            hits.append(
                {
                    "label": label,
                    "path": self.path,
                    "command": self.command,
                    "client": self.client_address[0],
                    "tls": isinstance(self.connection, ssl.SSLSocket),
                }
            )
            payload = PACKAGE_BODY if self.path.startswith("/packages/") else body
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args: object) -> None:
            return

    return Handler


class TlsServer:
    def __init__(self, certfile: str, keyfile: str, body: bytes, label: str) -> None:
        self.hits: list[dict[str, Any]] = []
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile, keyfile)
        self.httpd = _Threaded(("127.0.0.1", 0), _handler(body, self.hits, label))
        self.httpd.socket = ctx.wrap_socket(self.httpd.socket, server_side=True)
        self.port = int(self.httpd.server_address[1])
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self) -> "TlsServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class PlainHttpTrap:
    """Accepts plaintext HTTP so a downgrade retry would be visible."""

    def __init__(self) -> None:
        self.hits: list[dict[str, Any]] = []
        self.httpd = _Threaded(("127.0.0.1", 0), _handler(TRAP_BODY, self.hits, "http-trap"))
        self.port = int(self.httpd.server_address[1])
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.port80_bound = False
        self.port80_error: str | None = None
        self._port80: _Threaded | None = None
        self._port80_thread: threading.Thread | None = None

    def start(self) -> "PlainHttpTrap":
        self._thread.start()
        try:
            http80 = _Threaded(("127.0.0.1", 80), _handler(TRAP_BODY, self.hits, "http-port-80"))
            self._port80 = http80
            self._port80_thread = threading.Thread(target=http80.serve_forever, daemon=True)
            self._port80_thread.start()
            self.port80_bound = True
        except OSError as exc:
            self.port80_error = str(exc)
            self.port80_bound = False
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        if self._port80 is not None:
            try:
                self._port80.shutdown()
                self._port80.server_close()
            except OSError:
                pass


class FixtureCluster:
    def __init__(self, certs: FixtureCerts) -> None:
        self.certs = certs
        self.valid = TlsServer(str(certs.valid_crt), str(certs.valid_key), INDEX_BODY, "valid")
        self.wrong = TlsServer(str(certs.wrong_crt), str(certs.wrong_key), INDEX_BODY, "wrong-cn")
        self.expired = TlsServer(
            str(certs.expired_crt), str(certs.expired_key), INDEX_BODY, "expired"
        )
        self.trap = PlainHttpTrap()

    def start(self) -> "FixtureCluster":
        self.valid.start()
        self.wrong.start()
        self.expired.start()
        self.trap.start()
        return self

    def stop(self) -> None:
        for part in (self.valid, self.wrong, self.expired, self.trap):
            try:
                part.stop()
            except Exception:
                pass
