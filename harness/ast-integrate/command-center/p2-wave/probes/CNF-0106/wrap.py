"""In-process egress interceptor: log destinations, optionally block TCP connect."""
from __future__ import annotations

import socket
from contextlib import contextmanager
from typing import Any, Iterator

_orig_connect = socket.socket.connect
_orig_connect_ex = socket.socket.connect_ex


def _host_port(address: Any) -> tuple[str, int]:
    if isinstance(address, (tuple, list)) and len(address) >= 2:
        return str(address[0]), int(address[1])
    return str(address), 0


class EgressGuard:
    def __init__(self, block: bool) -> None:
        self.block = block
        self.attempts: list[dict[str, Any]] = []

    def record(self, host: str, port: int, via: str) -> None:
        self.attempts.append({"host": host, "port": port, "via": via, "blocked": self.block})

    def deny(self, host: str, port: int) -> OSError:
        return OSError(101, f"Network unreachable (CNF-0106 egress block) dest={host}:{port}")


@contextmanager
def install(block: bool) -> Iterator[EgressGuard]:
    guard = EgressGuard(block=block)

    def connect(self, address):  # noqa: ANN001
        host, port = _host_port(address)
        guard.record(host, port, "socket.connect")
        if guard.block:
            raise guard.deny(host, port)
        return _orig_connect(self, address)

    def connect_ex(self, address):  # noqa: ANN001
        host, port = _host_port(address)
        guard.record(host, port, "socket.connect_ex")
        if guard.block:
            return 101
        return _orig_connect_ex(self, address)

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    try:
        yield guard
    finally:
        socket.socket.connect = _orig_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = _orig_connect_ex  # type: ignore[method-assign]
