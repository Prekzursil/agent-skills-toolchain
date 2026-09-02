"""Passive connection capture at socket.create_connection (independent of the client)."""
from __future__ import annotations

import socket
from typing import Any


class ConnectionCapture:
    def __init__(self) -> None:
        self.attempts: list[dict[str, Any]] = []
        self._orig = socket.create_connection

    def __enter__(self) -> "ConnectionCapture":
        capture = self

        def wrapped(address, *args, **kwargs):  # type: ignore[no-untyped-def]
            host, port = address[0], int(address[1])
            capture.attempts.append(
                {
                    "host": host,
                    "port": port,
                    "scheme_guess": "http" if port == 80 else "tcp",
                }
            )
            return capture._orig(address, *args, **kwargs)

        socket.create_connection = wrapped  # type: ignore[assignment]
        return self

    def __exit__(self, *exc: object) -> None:
        socket.create_connection = self._orig  # type: ignore[assignment]

    def has_port(self, port: int) -> bool:
        return any(int(a["port"]) == int(port) for a in self.attempts)

    def has_plaintext_retry(self) -> bool:
        return any(int(a["port"]) == 80 or a.get("scheme_guess") == "http" for a in self.attempts)
