"""Process-wide network egress blocker for hermetic marketplace tests (IMP-0118).

``with egress_blocked():`` replaces the socket primitives every client library
funnels through - ``socket.create_connection``, ``socket.socket.connect`` /
``connect_ex`` / ``sendto`` and name resolution via ``socket.getaddrinfo`` - with
versions that raise :class:`EgressBlocked` (an ``OSError`` whose message carries
:data:`BLOCK_MSG`).  Nothing is sandboxed or mocked at a higher level: a test
that tries to fetch the real index fails loudly with the same error the probe
verifies against TEST-NET-1, which is what makes the "suite ran hermetically"
claim checkable in both states.

Every refused attempt is recorded on the block object (``attempts``) so a test
can assert that a code path really tried - or really did not try - to reach the
network.  Blocks nest; the originals are restored when the outermost block
exits.  ``allow_loopback=True`` lets 127.0.0.0/8 / ::1 / ``localhost`` through
for fixtures that run a local server; the default refuses everything.
"""
from __future__ import annotations

import errno
import ipaddress
import socket
import threading
from typing import Any

__all__ = [
    "BLOCK_MSG",
    "EgressBlock",
    "EgressBlocked",
    "egress_blocked",
    "is_egress_blocked",
]

BLOCK_MSG = "IMP-0118-EGRESS-BLOCKED"

_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"})

_lock = threading.RLock()
_originals: dict[str, Any] = {}
_stack: list["EgressBlock"] = []


class EgressBlocked(OSError):
    """Raised for any network attempt while an :class:`EgressBlock` is active."""

    def __init__(self, api: str, target: Any) -> None:
        super().__init__(errno.EPERM, f"{BLOCK_MSG}: {api} to {_describe(target)} refused")
        self.api = api
        self.target = target


def _describe(target: Any) -> str:
    if isinstance(target, tuple) and len(target) >= 2:
        return f"{target[0]}:{target[1]}"
    return repr(target)


def _host_of(target: Any) -> Any:
    if isinstance(target, tuple) and target:
        return target[0]
    return target


def _is_loopback(host: Any) -> bool:
    if isinstance(host, (bytes, bytearray)):
        try:
            host = bytes(host).decode("ascii")
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    text = host.strip().lower()
    if text in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(text.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _is_numeric_host(host: Any) -> bool:
    if isinstance(host, (bytes, bytearray)):
        try:
            host = bytes(host).decode("ascii")
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    try:
        ipaddress.ip_address(host.strip().split("%", 1)[0])
    except ValueError:
        return False
    return True


class EgressBlock:
    """The active blocker; use through :func:`egress_blocked`.

    ``attempts`` lists every refused call as ``{"api": ..., "target": ...}``;
    ``allowed`` lists loopback calls that were let through (only with
    ``allow_loopback=True``).
    """

    def __init__(self, *, allow_loopback: bool = False) -> None:
        self.allow_loopback = bool(allow_loopback)
        self.attempts: list[dict[str, Any]] = []
        self.allowed: list[dict[str, Any]] = []
        self.active = False

    def __repr__(self) -> str:
        state = "active" if self.active else "inactive"
        return f"EgressBlock({state}, refused={len(self.attempts)}, allow_loopback={self.allow_loopback})"

    # -- policy -----------------------------------------------------------------

    def permits(self, target: Any) -> bool:
        """Whether a connection to ``target`` would be let through under this block."""
        return self.allow_loopback and _is_loopback(_host_of(target))

    def _refuse(self, api: str, target: Any) -> None:
        self.attempts.append({"api": api, "target": _describe(target)})
        raise EgressBlocked(api, target)

    def _gate(self, api: str, target: Any) -> None:
        if self.permits(target):
            self.allowed.append({"api": api, "target": _describe(target)})
            return
        self._refuse(api, target)

    # -- context manager ----------------------------------------------------------

    def __enter__(self) -> "EgressBlock":
        with _lock:
            if not _stack:
                _install()
            _stack.append(self)
            self.active = True
        return self

    def __exit__(self, *_exc: object) -> None:
        with _lock:
            self.active = False
            if self in _stack:
                _stack.remove(self)
            if not _stack:
                _restore()


def _current() -> EgressBlock | None:
    with _lock:
        return _stack[-1] if _stack else None


def _blocked_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
    block = _current()
    if block is None:
        return _originals["create_connection"](address, *args, **kwargs)
    block._gate("create_connection", address)
    return _originals["create_connection"](address, *args, **kwargs)


def _blocked_connect(self: socket.socket, address: Any) -> Any:
    block = _current()
    if block is not None:
        block._gate("connect", address)
    return _originals["connect"](self, address)


def _blocked_connect_ex(self: socket.socket, address: Any) -> Any:
    block = _current()
    if block is not None:
        block._gate("connect_ex", address)
    return _originals["connect_ex"](self, address)


def _blocked_sendto(self: socket.socket, *args: Any) -> Any:
    block = _current()
    if block is not None and args:
        block._gate("sendto", args[-1])
    return _originals["sendto"](self, *args)


def _blocked_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
    block = _current()
    if block is not None and host is not None and not _is_numeric_host(host):
        # Numeric literals never leave the process; a name lookup is a DNS query.
        block._gate("getaddrinfo", host)
    return _originals["getaddrinfo"](host, *args, **kwargs)


def _install() -> None:
    _originals["create_connection"] = socket.create_connection
    _originals["connect"] = socket.socket.connect
    _originals["connect_ex"] = socket.socket.connect_ex
    _originals["sendto"] = socket.socket.sendto
    _originals["getaddrinfo"] = socket.getaddrinfo
    socket.create_connection = _blocked_create_connection  # type: ignore[assignment]
    socket.socket.connect = _blocked_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _blocked_connect_ex  # type: ignore[method-assign]
    socket.socket.sendto = _blocked_sendto  # type: ignore[method-assign]
    socket.getaddrinfo = _blocked_getaddrinfo  # type: ignore[assignment]


def _restore() -> None:
    if not _originals:
        return
    socket.create_connection = _originals["create_connection"]  # type: ignore[assignment]
    socket.socket.connect = _originals["connect"]  # type: ignore[method-assign]
    socket.socket.connect_ex = _originals["connect_ex"]  # type: ignore[method-assign]
    socket.socket.sendto = _originals["sendto"]  # type: ignore[method-assign]
    socket.getaddrinfo = _originals["getaddrinfo"]  # type: ignore[assignment]
    _originals.clear()


def egress_blocked(*, allow_loopback: bool = False) -> EgressBlock:
    """Context manager that refuses every network egress attempt with :data:`BLOCK_MSG`.

    ``socket.create_connection(("192.0.2.1", 80))`` inside the block raises an
    ``OSError`` whose text contains ``IMP-0118-EGRESS-BLOCKED``; so does any
    ``connect``/``sendto`` on a socket object and any non-numeric name lookup.
    """
    return EgressBlock(allow_loopback=allow_loopback)


def is_egress_blocked() -> bool:
    """True while at least one :class:`EgressBlock` is active in this process."""
    return _current() is not None
