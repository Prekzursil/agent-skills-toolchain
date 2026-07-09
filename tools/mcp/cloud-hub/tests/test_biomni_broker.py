#!/usr/bin/env python3
"""Unit tests for the Biomni localhost token-broker (``biomni-mcp/broker.py``).

Exercises the security-critical, network-free logic: secure-source resolution +
priority, the header rewrite that OVERWRITES Authorization (the whole point), TTL
caching for rotation, and masking. The module is loaded by explicit path as
``biomni_broker`` so it never collides with the other ``server.py`` wrappers."""

from __future__ import annotations

import importlib.util
import os
import sys

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
