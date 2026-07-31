#!/usr/bin/env python3
"""mcp-liveness: an `initialize` answer alone must not certify the keystone "up".

The defect this pins: ``probe_critical`` accepted ANY JSON-RPC ``result``/``error``
as proof of health, so a listener that speaks MCP but exposes no tools -- a
different server that grabbed :8765, or a basic-memory whose write/read surface is
gone -- was reported ``state="up"``, ``mcp_ok=True``. SessionStart then emitted no
warning, attempted no restart, and saved ``last_state="up"`` while semantic memory
was unusable. Monitoring the promise, not the capability.

The sibling ``test_liveness.py`` cannot catch it: its "corpse" control serves a
NON-MCP body, so it exercises the handshake-fails path, never the
handshake-succeeds-but-useless path. It is also not collected by CI -- it has no
``test_*`` functions and ``quality.yml`` never names it -- whereas this module is a
plain pytest file inside ``hooks/``, so the existing
``python -m pytest hooks/ -q --import-mode=importlib`` step runs it.

Every assertion here is paired with its opposite state, so a guard that rejected
everything (a false DOWN, which would be a WORSE failure than the false green)
cannot pass as a fix.
"""

from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "_c06_liveness_under_test", HERE / "liveness.py"
)
assert _SPEC is not None and _SPEC.loader is not None
liveness = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(liveness)

CFG = {"tcp_timeout": 1.5, "handshake_timeout": 5.0}


def _handler_for(result: dict):
    class _H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
            # DRAIN THE REQUEST BODY FIRST. Skipping this closes the socket with
            # unread bytes still buffered, which on Windows makes the peer send RST:
            # urlopen then raises ConnectionResetError, liveness catches OSError and
            # returns None, and the probe reports "dead-listening" for a HEALTHY
            # server. That made this suite flaky AND made one assertion pass for
            # entirely the wrong reason.
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_a):
            return

    return _H


@pytest.fixture()
def serve():
    started: list[ThreadingHTTPServer] = []

    def _start(result: dict) -> dict:
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(result))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        started.append(srv)
        port = srv.server_address[1]
        return {
            "host": "127.0.0.1",
            "port": port,
            "url": f"http://127.0.0.1:{port}/mcp",
        }

    yield _start
    for srv in started:
        srv.shutdown()


_TOOL_SERVER = {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}, "resources": {}},
    "serverInfo": {"name": "basic-memory", "version": "1.0"},
}
_INIT_ONLY_SERVER = {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "serverInfo": {"name": "not-basic-memory", "version": "1.0"},
}


def test_init_only_listener_is_not_reported_up(serve):
    """THE DEFECT. Before the fix this returned state='up', mcp_ok=True."""

    spec = serve(_INIT_ONLY_SERVER)
    r = liveness.probe_critical("basic-memory", spec, CFG)

    assert r["state"] == "dead-listening"
    assert r["tools_ok"] is False
    assert "tools" in r["mismatch"]
    assert "not-basic-memory" in r["mismatch"], (
        "the alert must name who actually holds the port"
    )


def test_tool_serving_listener_is_reported_up(serve):
    """CONTROL for the assertion above. Without it, a guard that demoted EVERY
    server would satisfy the test while breaking the keystone with a false DOWN."""

    r = liveness.probe_critical("basic-memory", serve(_TOOL_SERVER), CFG)

    assert r["state"] == "up"
    assert r["mcp_ok"] is True and r["tools_ok"] is True
    assert r["mismatch"] == ""


def test_false_green_now_produces_an_operator_alert(serve):
    spec = serve(_INIT_ONLY_SERVER)
    r = liveness.probe_critical("basic-memory", spec, CFG)

    alert = liveness.format_alert([r], [], False)
    assert "WRONG SERVER" in alert
    assert "not-basic-memory" in alert


@pytest.mark.parametrize(
    "result",
    [
        {"protocolVersion": "2024-11-05"},  # no capabilities map at all
        {"capabilities": "tools"},  # capabilities present but not a map
    ],
)
def test_undecidable_handshakes_stay_up(serve, result):
    """One-directional by design: only a decoded ``capabilities`` map that OMITS
    ``tools`` demotes. Anything ambiguous must remain 'up' -- inventing a DOWN for
    the keystone would trigger spurious restarts of a healthy vault."""

    assert liveness.probe_critical("basic-memory", serve(result), CFG)["state"] == "up"


def test_require_tools_false_opts_a_server_out(serve):
    spec = {**serve(_INIT_ONLY_SERVER), "require_tools": False}
    assert liveness.probe_critical("other-mcp", spec, CFG)["state"] == "up"


def test_serves_tools_is_inconclusive_without_a_parsed_body():
    """A streamable-http session handshake (400/405/...) yields no body: the
    handshake counted as MCP but there is nothing to inspect."""

    assert liveness.serves_tools(None, {}) == (True, "")
    assert liveness.serves_tools({"error": {"code": -32601}}, {}) == (True, "")


def test_mcp_handshake_keeps_its_tri_state_contract(serve):
    """``mcp_handshake`` is public API used by test_liveness.py; the refactor to
    ``handshake_detail`` must not change what it returns."""

    assert liveness.mcp_handshake(serve(_TOOL_SERVER)["url"], 5.0) is True
    assert liveness.mcp_handshake("http://127.0.0.1:1/mcp", 1.0) is None
