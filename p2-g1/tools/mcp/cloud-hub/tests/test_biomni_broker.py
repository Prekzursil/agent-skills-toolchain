#!/usr/bin/env python3
"""Unit tests for the Biomni localhost token-broker (``biomni-mcp/broker.py``).

Exercises the security-critical, network-free logic: secure-source resolution +
priority, the header rewrite that OVERWRITES Authorization (the whole point), TTL
caching for rotation, and masking. The module is loaded by explicit path as
``biomni_broker`` so it never collides with the other ``server.py`` wrappers."""

from __future__ import annotations

import contextlib
import http.server
import importlib.util
import json
import os
import sys
import threading
import urllib.error
import urllib.request

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

_PATH = os.path.join(HUB_DIR, "biomni-mcp", "broker.py")
_spec = importlib.util.spec_from_file_location("biomni_broker", _PATH)
biomni_broker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(biomni_broker)


# --------------------------------------------------------------------------- #
# Secure-source resolution + priority
# --------------------------------------------------------------------------- #
def test_resolve_from_env():
    env = {"BIOMNI_BROKER_TOKEN": "t-env", "BIOMNI_BROKER_TOKEN_FILE": "/no/such/file"}
    assert biomni_broker.resolve_token_uncached(env) == ("t-env", "env")


def test_resolve_from_file(tmp_path):
    f = tmp_path / "broker_token"
    f.write_text("t-file\n", encoding="utf-8")
    env = {"BIOMNI_BROKER_TOKEN_FILE": str(f), "BIOMNI_BROKER_TOKEN": "t-env"}
    # File beats env in the priority order.
    assert biomni_broker.resolve_token_uncached(env) == ("t-file", "file")


def test_resolve_op_takes_priority(monkeypatch):
    monkeypatch.setattr(biomni_broker, "_op_read", lambda ref: "t-op")
    env = {
        "BIOMNI_BROKER_OP_REF": "op://vault/biomni/token",
        "BIOMNI_BROKER_TOKEN": "t-env",
        "BIOMNI_BROKER_TOKEN_FILE": "/no/such/file",
    }
    assert biomni_broker.resolve_token_uncached(env) == ("t-op", "op")


def test_resolve_none_when_nothing_set():
    env = {"BIOMNI_BROKER_TOKEN_FILE": "/no/such/file"}
    assert biomni_broker.resolve_token_uncached(env) == ("", "none")


# --------------------------------------------------------------------------- #
# The header rewrite — the security-critical property
# --------------------------------------------------------------------------- #
def test_upstream_headers_cookie_default_and_strips_incoming_auth():
    incoming = [
        ("Authorization", "Bearer DUMMY-FROM-CONNECTOR"),
        ("Cookie", "session_id=STALE"),
        ("Host", "127.0.0.1:8787"),
        ("Content-Length", "5"),
        ("Connection", "keep-alive"),
        ("X-Custom", "keepme"),
        ("Accept", "application/json"),
    ]
    out = biomni_broker.upstream_headers(incoming, "REAL-SESSION", "api.phylo.bio")
    # Default is COOKIE mode (Biomni's real auth): inject the real session cookie,
    # drop the connector's Authorization AND its stale Cookie; Host points upstream.
    assert out["Cookie"] == "session_id=REAL-SESSION"
    assert "Authorization" not in out
    assert out["Host"] == "api.phylo.bio"
    # Hop-by-hop + length are stripped; benign headers pass through.
    assert "Content-Length" not in out and "Connection" not in out
    assert out["X-Custom"] == "keepme" and out["Accept"] == "application/json"
    # Neither the connector's dummy Bearer nor its stale cookie survives.
    assert "DUMMY-FROM-CONNECTOR" not in "".join(out.values())
    assert "STALE" not in "".join(out.values())


def test_upstream_headers_bearer_mode():
    out = biomni_broker.upstream_headers(
        [("Accept", "application/json")], "TOK", "api.phylo.bio", auth_mode="bearer"
    )
    assert out["Authorization"] == "Bearer TOK" and "Cookie" not in out


# --------------------------------------------------------------------------- #
# TTL cache (rotation pickup) + masking
# --------------------------------------------------------------------------- #
def test_cache_refreshes_after_ttl():
    env = {"BIOMNI_BROKER_TOKEN": "a", "BIOMNI_BROKER_TOKEN_FILE": "/no/such/file"}
    clock = {"t": 1000.0}
    cache = biomni_broker.TokenCache(env, ttl=60.0, clock=lambda: clock["t"])
    assert cache.get() == ("a", "env")
    env["BIOMNI_BROKER_TOKEN"] = "b"
    clock["t"] += 10  # within TTL -> still cached
    assert cache.get() == ("a", "env")
    clock["t"] += 100  # past TTL -> re-resolved
    assert cache.get() == ("b", "env")


def test_mask_never_reveals_full_token():
    assert biomni_broker._mask("abcdefghij") == "...ghij"
    assert biomni_broker._mask("short") == "set"
    assert biomni_broker._mask("") == ""


# --------------------------------------------------------------------------- #
# LOCAL CLIENT AUTHORIZATION -- loopback reachability is NOT authorization.     #
# --------------------------------------------------------------------------- #
class _Upstream(http.server.BaseHTTPRequestHandler):
    """A fake api.phylo.bio that records exactly what the broker forwarded."""

    seen: list = []

    def log_message(self, fmt, *args):
        return

    def _record(self):
        _Upstream.seen.append(
            {
                "method": self.command,
                "path": self.path,
                "cookie": self.headers.get("Cookie"),
                "authorization": self.headers.get("Authorization"),
                "client_cap": self.headers.get(biomni_broker.CLIENT_AUTH_HEADER),
            }
        )
        body = b'{"deleted": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _record


@contextlib.contextmanager
def _serving(handler_cls):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(5)


@contextlib.contextmanager
def _broker(capability, token="PROBE-SECRET"):
    _Upstream.seen = []
    with _serving(_Upstream) as upstream:
        # BIOMNI_BROKER_TOKEN_FILE MUST be pinned: unset, resolve_token_uncached
        # falls back to ~/.biomni-mcp/broker_token and the test would read (and
        # forward) the developer's REAL stored session instead of the fixture.
        cache = biomni_broker.TokenCache(
            {"BIOMNI_BROKER_TOKEN": token, "BIOMNI_BROKER_TOKEN_FILE": "/no/such/file"},
            ttl=60.0,
        )
        handler = biomni_broker.make_handler(upstream, cache, capability)
        with _serving(handler) as broker_url:
            yield broker_url


def _call(url, method, headers=None):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def test_unauthenticated_local_request_is_refused_before_injection():
    """Any local process could DELETE the user projects with the real session."""
    with _broker("CAP-SECRET") as broker_url:
        status, body = _call(broker_url + "/v2/projects/probe-project", "DELETE")
    assert status == 401, body
    # The decisive assertion: the upstream was never reached, so the stored Biomni
    # cookie was never attached to an unauthorized local caller's request.
    assert _Upstream.seen == []


def test_authorized_client_is_proxied_and_the_capability_never_leaks_upstream():
    with _broker("CAP-SECRET") as broker_url:
        status, body = _call(
            broker_url + "/v2/projects/probe-project",
            "DELETE",
            {biomni_broker.CLIENT_AUTH_HEADER: "CAP-SECRET"},
        )
    assert (status, body) == (200, b'{"deleted": true}')
    assert len(_Upstream.seen) == 1
    seen = _Upstream.seen[0]
    assert seen["method"] == "DELETE"
    assert seen["cookie"] == "session_id=PROBE-SECRET"
    # The client capability is a LOCAL credential -- it must be stripped.
    assert seen["client_cap"] is None


def test_bearer_form_of_the_capability_is_accepted():
    with _broker("CAP-SECRET") as broker_url:
        status, _ = _call(
            broker_url + "/v2/ping", "GET", {"Authorization": "Bearer CAP-SECRET"}
        )
    assert status == 200


def test_wrong_capability_is_refused():
    with _broker("CAP-SECRET") as broker_url:
        status, _ = _call(
            broker_url + "/v2/ping",
            "GET",
            {biomni_broker.CLIENT_AUTH_HEADER: "CAP-WRONG"},
        )
    assert status == 401
    assert _Upstream.seen == []


def test_health_stays_reachable_without_the_capability():
    with _broker("CAP-SECRET") as broker_url:
        status, body = _call(broker_url + biomni_broker.HEALTH_PATH, "GET")
    assert status == 200
    payload = json.loads(body)
    assert payload["ok"] is True and payload["token_present"] is True
    text = body.decode()
    assert "PROBE-SECRET" not in text and "CAP-SECRET" not in text


def test_resolve_client_capability_env_beats_file(tmp_path):
    path = tmp_path / "client_token"
    path.write_text("from-file", encoding="utf-8")
    env = {
        "BIOMNI_BROKER_CLIENT_TOKEN": "from-env",
        "BIOMNI_BROKER_CLIENT_TOKEN_FILE": str(path),
    }
    assert biomni_broker.resolve_client_capability(env) == ("from-env", "env")


def test_resolve_client_capability_mints_once_and_persists(tmp_path):
    path = tmp_path / "sub" / "client_token"
    env = {"BIOMNI_BROKER_CLIENT_TOKEN_FILE": str(path)}
    minted, source = biomni_broker.resolve_client_capability(env)
    assert source == "minted" and len(minted) >= 32
    assert path.read_text(encoding="utf-8") == minted
    # A second broker (or the connector) reads the SAME capability back.
    assert biomni_broker.resolve_client_capability(env) == (minted, "file")


def test_an_empty_capability_can_never_authorize():
    """A misconfigured broker must fail closed, not open."""
    assert biomni_broker.client_authorized({}, "") is False
    assert (
        biomni_broker.client_authorized({biomni_broker.CLIENT_AUTH_HEADER: ""}, "")
        is False
    )
