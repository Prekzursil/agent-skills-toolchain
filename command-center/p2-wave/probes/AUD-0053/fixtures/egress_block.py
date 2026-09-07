"""AUD-0053 socket-level egress blocker.

Deliberately patches at the LOWEST level -- `socket.socket.connect` /
`connect_ex` -- so it blocks urllib, http.client, requests, and raw sockets
alike; whatever library sits on top, they all eventually call
`socket.socket.connect()` (or its non-blocking cousin `connect_ex`) to
establish the underlying TCP connection, including the TLS handshake for
HTTPS (TLS wraps an already-connected socket, so blocking connect() blocks
HTTPS too, before any bytes of the handshake are sent).

Loopback (127.0.0.1 / ::1 / "localhost") is allowed through unpatched so a
test that talks to a local fixture server does not get flagged as an egress
dependency it does not have.

`install()` / `uninstall()` are idempotent and reversible -- this module is
imported directly (not just via the pytest plugin) by probe1's own
both-states control, which must prove the block actually blocks a real fetch
*and* prove an unblocked fetch actually succeeds, in the same process,
before either probe trusts the pytest subprocess results.
"""

from __future__ import annotations

import socket

_ORIG_CONNECT = socket.socket.connect
_ORIG_CONNECT_EX = socket.socket.connect_ex
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_installed = False


def _is_loopback(address: object) -> bool:
    try:
        host = address[0] if isinstance(address, tuple) else address
    except Exception:  # noqa: BLE001
        return False
    return host in _LOOPBACK_HOSTS


def _blocked_connect(self: socket.socket, address: object) -> None:
    if _is_loopback(address):
        _ORIG_CONNECT(self, address)  # type: ignore[misc]
        return
    raise OSError(
        111,
        f"AUD-0053 egress-blocked: connect() to {address!r} refused by the probe's "
        "socket-level block (fixtures/egress_block.py); loopback only",
    )


def _blocked_connect_ex(self: socket.socket, address: object) -> int:
    if _is_loopback(address):
        return _ORIG_CONNECT_EX(self, address)  # type: ignore[misc]
    return 111  # ECONNREFUSED-shaped, matching the raised OSError's errno above


def install() -> None:
    global _installed
    if _installed:
        return
    socket.socket.connect = _blocked_connect  # type: ignore[assignment]
    socket.socket.connect_ex = _blocked_connect_ex  # type: ignore[assignment]
    _installed = True


def uninstall() -> None:
    global _installed
    if not _installed:
        return
    socket.socket.connect = _ORIG_CONNECT  # type: ignore[assignment]
    socket.socket.connect_ex = _ORIG_CONNECT_EX  # type: ignore[assignment]
    _installed = False


def is_installed() -> bool:
    return _installed
