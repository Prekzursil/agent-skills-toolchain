"""AUD-0053 probe support plugin: egress block/trace plus outcome+connection recorders.

Registered into a pytest subprocess via `-p aud0053_plugin` (fixtures/ on
PYTHONPATH). Three responsibilities, kept in ONE plugin so hook ordering
between "install the block/tracer" and "record what happened" is never
ambiguous:

1. --aud0053-block-egress: installs fixtures/egress_block.py's socket-level
   block in pytest_configure, i.e. BEFORE collection starts -- so even a
   network call made at import/collection time (not just inside a test body)
   is blocked. This is what probe1's "blocked run" uses.
2. --aud0053-trace-egress: instead of blocking, wraps socket.socket.connect
   so every non-loopback destination is recorded against whichever test's
   nodeid is currently executing. This is the "socket-level trace ... naming
   the destination hosts" the catalog names as probe2's evidence_requirement.
   Mutually exclusive with --aud0053-block-egress (block wins if both given).
3. AUD0053_RESULTS_PATH / AUD0053_CONNECTIONS_PATH env vars: writes
   {nodeid: outcome} and the ordered connection-attempt list to JSON files,
   so probe1/probe2 can read verbatim recorded data without depending on an
   unlisted pytest-json-report package.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import egress_block  # noqa: E402

_RESULTS: dict[str, str] = {}
_CONNECTIONS: list[dict] = []
_CURRENT_NODEID: str | None = None
_ORIG_CONNECT = socket.socket.connect
_tracing = False


def pytest_addoption(parser: object) -> None:
    parser.addoption(  # type: ignore[attr-defined]
        "--aud0053-block-egress",
        action="store_true",
        default=False,
        help="AUD-0053 probe1: install the socket-level egress block before collection",
    )
    parser.addoption(  # type: ignore[attr-defined]
        "--aud0053-trace-egress",
        action="store_true",
        default=False,
        help="AUD-0053 probe2: trace (do not block) every non-loopback connect() per test",
    )


def _traced_connect(self: socket.socket, address: object):
    try:
        host = address[0] if isinstance(address, tuple) else str(address)
        port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
    except Exception:  # noqa: BLE001
        host, port = str(address), None
    if host not in ("127.0.0.1", "::1", "localhost"):
        _CONNECTIONS.append({"nodeid": _CURRENT_NODEID, "host": host, "port": port})
    return _ORIG_CONNECT(self, address)  # type: ignore[misc]


def pytest_configure(config: object) -> None:
    global _tracing
    if config.getoption("--aud0053-block-egress"):  # type: ignore[attr-defined]
        egress_block.install()
    elif config.getoption("--aud0053-trace-egress"):  # type: ignore[attr-defined]
        socket.socket.connect = _traced_connect  # type: ignore[assignment]
        _tracing = True


def pytest_unconfigure(config: object) -> None:
    global _tracing
    if egress_block.is_installed():
        egress_block.uninstall()
    if _tracing:
        socket.socket.connect = _ORIG_CONNECT  # type: ignore[assignment]
        _tracing = False


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: object, nextitem: object):  # type: ignore[no-untyped-def]
    global _CURRENT_NODEID
    _CURRENT_NODEID = item.nodeid  # type: ignore[attr-defined]
    yield
    _CURRENT_NODEID = None


def pytest_runtest_logreport(report: object) -> None:
    if getattr(report, "when", None) != "call":
        return
    _RESULTS[report.nodeid] = report.outcome  # type: ignore[attr-defined]


def pytest_sessionfinish(session: object, exitstatus: object) -> None:
    results_path = os.environ.get("AUD0053_RESULTS_PATH")
    if results_path:
        Path(results_path).write_text(
            json.dumps(_RESULTS, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
    conns_path = os.environ.get("AUD0053_CONNECTIONS_PATH")
    if conns_path:
        Path(conns_path).write_text(
            json.dumps(_CONNECTIONS, indent=1) + "\n", encoding="utf-8"
        )
    _RESULTS.clear()
    _CONNECTIONS.clear()
