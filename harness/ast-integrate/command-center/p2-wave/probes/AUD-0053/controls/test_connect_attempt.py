"""Planted DEPEND control: PASS iff the environment permits an egress attempt.

Blocked hook raises OSError with 'AUD-0053 blocked' -> FAIL.
Unblocked hook delegates; OS timeout/refused is still PASS because the
attempt was allowed. That separates DEPEND from TOUCH on an air-gapped host.
"""
from __future__ import annotations

import socket

HOST = "bootstrap.pypa.io"
PORT = 443


def test_connect_attempt_permitted() -> None:
    try:
        sock = socket.create_connection((HOST, PORT), timeout=2.0)
    except OSError as exc:
        if "AUD-0053 blocked" in str(exc):
            raise AssertionError(f"egress blocked: {exc}") from exc
        return
    sock.close()
