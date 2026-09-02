#!/usr/bin/env python3
"""Exercise fb_session._mcp_whoami over a REAL stdio MCP round-trip.

Uses the existing fake/broken backends plus a tiny inline backend that returns a
uid, so both the authenticated and unauthenticated parses run against the real
JSON-RPC handshake (not a mock).
"""

from __future__ import annotations

import os
import sys

import fb_session as S

_TESTS = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def test_mcp_whoami_roundtrip_not_authed():
    # fake_backend echoes the call; no uid field -> not authenticated, but the
    # full initialize + tools/call round-trip is exercised for real.
    cmd = (PY, os.path.join(_TESTS, "fake_backend.py"), "fb", "whoami")
    v = S._mcp_whoami(cmd, dict(os.environ))
    assert v["authenticated"] is False


def test_mcp_whoami_backend_dies():
    cmd = (PY, os.path.join(_TESTS, "broken_backend.py"))
    v = S._mcp_whoami(cmd, dict(os.environ))
    assert v["authenticated"] is False
    assert v["name_present"] is False


def test_mcp_whoami_authenticated(tmp_path):
    backend = tmp_path / "uid_backend.py"
    backend.write_text(
        "import json,sys\n"
        "for raw in sys.stdin:\n"
        "    raw=raw.strip()\n"
        "    if not raw.startswith('{'): continue\n"
        "    m=json.loads(raw); mid=m.get('id'); meth=m.get('method')\n"
        "    if meth=='initialize':\n"
        "        sys.stdout.write(json.dumps({'jsonrpc':'2.0','id':mid,"
        "'result':{'protocolVersion':'2024-11-05','capabilities':{},"
        "'serverInfo':{'name':'u','version':'1'}}})+chr(10)); sys.stdout.flush()\n"
        "    elif meth=='tools/call':\n"
        "        sys.stdout.write(json.dumps({'jsonrpc':'2.0','id':mid,'result':{'content':"
        "[{'type':'text','text':json.dumps({'uid':'42','name':'Owner'})}]}})+chr(10));"
        " sys.stdout.flush()\n",
        encoding="utf-8",
    )
    v = S._mcp_whoami((PY, str(backend)), dict(os.environ))
    assert v["authenticated"] is True
    assert v["name_present"] is True
    # still never leaks the value
    assert "42" not in v["detail"] and "Owner" not in v["detail"]
