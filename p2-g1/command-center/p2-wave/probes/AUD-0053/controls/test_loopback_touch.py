"""Planted loopback TOUCH: socket use that is not egress.

Allowed under the block (loopback is not egress). Trace must name 127.0.0.1
and must not classify this file as depends_on_egress.
"""
from __future__ import annotations

import socket


def test_loopback_connect() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        cli = socket.create_connection(("127.0.0.1", port), timeout=2.0)
        conn, _addr = srv.accept()
        try:
            cli.sendall(b"AUD-0053")
            got = conn.recv(16)
        finally:
            conn.close()
            cli.close()
    finally:
        srv.close()
    if got != b"AUD-0053":
        raise AssertionError(got)
