"""Local registry fixture that can reset after N of M bytes (TST-0131)."""
from __future__ import annotations

import socket
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from urllib.parse import parse_qs, urlparse

PACKAGE_ID = "tst0131-demo-pkg"
TRUNCATE_AFTER = 8192


def fixture_blob() -> bytes:
    header = b"TST-0131-fixture-v1\n"
    body = bytes((i * 17 + 31) % 256 for i in range(65536))
    return header + body


class _Handler(BaseHTTPRequestHandler):
    blob: bytes = b""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        blob = self.server.blob  # type: ignore[attr-defined]
        if parsed.path not in (f"/packages/{PACKAGE_ID}", f"/pkg/{PACKAGE_ID}"):
            self.send_response(404)
            self.end_headers()
            return
        n_raw = qs.get("reset_after") or qs.get("truncate")
        n = int(n_raw[0]) if n_raw else None
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Connection", "close")
        self.end_headers()
        payload = blob if n is None else blob[:n]
        try:
            self.wfile.write(payload)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        if n is not None:
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.close_connection = True

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        return


@contextmanager
def serve_blob(blob: bytes) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.blob = blob
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()


def full_url(base: str, package_id: str = PACKAGE_ID) -> str:
    return f"{base}/packages/{package_id}"


def truncate_url(
    base: str,
    n: int = TRUNCATE_AFTER,
    package_id: str = PACKAGE_ID,
) -> str:
    return f"{base}/packages/{package_id}?reset_after={n}"


def listing_names_package(hits: list[str], package_id: str) -> bool:
    needle = package_id
    return any(needle in h for h in hits)


def quarantine_is_outside_cache(qpath: Path, cache_root: Path) -> bool:
    q = Path(qpath).resolve()
    c = Path(cache_root).resolve()
    try:
        q.relative_to(c)
        return False
    except ValueError:
        return True
