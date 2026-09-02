"""Local registry fixture: immediate accept, then trickle or full-speed body."""
from __future__ import annotations

import socket
import threading
import time
from typing import Optional

from scenario import FAST_BODY, SLOW_BODY_LEN, TRICKLE_INTERVAL_S


class LorisServer:
    """TCP HTTP/1.1 fixture bound to 127.0.0.1.

    `/fast` writes a complete response at once.
    `/slow` trickles one byte at a time after the request is fully read,
    so the TCP handshake (and therefore connect-timeout) has already
    succeeded.
    """

    def __init__(
        self,
        *,
        trickle_interval_s: float = TRICKLE_INTERVAL_S,
        slow_body_len: int = SLOW_BODY_LEN,
        fast_body: bytes = FAST_BODY,
    ):
        self.trickle_interval_s = trickle_interval_s
        self.slow_body_len = slow_body_len
        self.fast_body = fast_body
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.host = "127.0.0.1"
        self.port = 0
        self.accepted = 0
        self._lock = threading.Lock()

    @property
    def fast_url(self) -> str:
        return f"http://{self.host}:{self.port}/fast"

    @property
    def slow_url(self) -> str:
        return f"http://{self.host}:{self.port}/slow"

    def __enter__(self) -> "LorisServer":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, 0))
        sock.listen(16)
        sock.settimeout(0.2)
        self.port = int(sock.getsockname()[1])
        self._sock = sock
        self._thread = threading.Thread(target=self._loop, name="tst0132-loris", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._stop.set()
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self._lock:
                self.accepted += 1
            worker = threading.Thread(
                target=self._handle, args=(conn,), name="tst0132-conn", daemon=True
            )
            worker.start()

    def _handle(self, conn: socket.socket) -> None:
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn.settimeout(2.0)
            req = b""
            while b"\r\n\r\n" not in req and not self._stop.is_set():
                try:
                    chunk = conn.recv(2048)
                except socket.timeout:
                    return
                if not chunk:
                    return
                req += chunk
            first = req.split(b"\r\n", 1)[0].decode("latin-1", "replace")
            path = "/"
            parts = first.split()
            if len(parts) >= 2:
                path = parts[1].split("?", 1)[0]
            if path.endswith("/fast"):
                self._send_fast(conn)
            else:
                self._send_slow(conn)
        except OSError:
            return
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _send_fast(self, conn: socket.socket) -> None:
        body = self.fast_body
        header = (
            "HTTP/1.1 200 OK\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ascii")
        conn.sendall(header + body)

    def _send_slow(self, conn: socket.socket) -> None:
        header = (
            "HTTP/1.1 200 OK\r\n"
            f"Content-Length: {self.slow_body_len}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ascii")
        payload = header + (b"L" * self.slow_body_len)
        conn.settimeout(1.0)
        for i in range(len(payload)):
            if self._stop.is_set():
                break
            try:
                conn.sendall(payload[i : i + 1])
            except OSError:
                break
            time.sleep(self.trickle_interval_s)
