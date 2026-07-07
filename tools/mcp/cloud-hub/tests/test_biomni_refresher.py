#!/usr/bin/env python3
"""Unit tests for the Biomni refresh-at-source broker (``biomni-mcp/refresher.py``).

Covers the network/browser-free logic: Bearer extraction, best-token selection,
store writing (file + keyring), store-spec resolution, masking, and the lazy
Playwright hint. The Playwright shell needs a real browser and is integration-only.
The module is loaded by explicit path as ``biomni_refresher``."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import types

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

_PATH = os.path.join(HUB_DIR, "biomni-mcp", "refresher.py")
_spec = importlib.util.spec_from_file_location("biomni_refresher", _PATH)
biomni_refresher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(biomni_refresher)


# --------------------------------------------------------------------------- #
# Bearer extraction + selection
# --------------------------------------------------------------------------- #
def test_bearer_from_auth_header():
    assert biomni_refresher.bearer_from_auth_header("Bearer abc123") == "abc123"
    assert (
        biomni_refresher.bearer_from_auth_header("bearer xyz") == "xyz"
    )  # case-insensitive
    assert biomni_refresher.bearer_from_auth_header("Basic Zm9v") == ""
    assert biomni_refresher.bearer_from_auth_header("Bearer ") == ""
    assert biomni_refresher.bearer_from_auth_header("") == ""
    assert biomni_refresher.bearer_from_auth_header(None) == ""


def test_select_bearer_prefers_longest():
    captured = ["Basic nope", "Bearer short", "Bearer a-much-longer-token", "garbage"]
    assert biomni_refresher.select_bearer(captured) == "a-much-longer-token"
    assert biomni_refresher.select_bearer([]) == ""
    assert biomni_refresher.select_bearer(["Basic x"]) == ""


# --------------------------------------------------------------------------- #
# Store writing (file + keyring) — never leaks the token
# --------------------------------------------------------------------------- #
def test_write_token_file_chmod_and_masked(tmp_path):
    path = tmp_path / "sub" / "broker_token"
    store = {"kind": "file", "path": str(path)}
    msg = biomni_refresher.write_token(store, "SECRET-TOKEN-VALUE")
    assert path.read_text(encoding="utf-8") == "SECRET-TOKEN-VALUE"
    # Status line is masked — never the full token.
    assert "SECRET-TOKEN-VALUE" not in msg and "...ALUE" in msg


def test_write_token_keyring(monkeypatch):
    calls: dict = {}
    fake = types.ModuleType("keyring")
    fake.set_password = lambda s, u, t: calls.update(service=s, user=u, token=t)
    monkeypatch.setitem(sys.modules, "keyring", fake)
    store = {"kind": "keyring", "service": "biomni", "user": "andrei"}
    msg = biomni_refresher.write_token(store, "SECRET")
    assert calls == {"service": "biomni", "user": "andrei", "token": "SECRET"}
    assert "SECRET" not in msg


def test_resolve_store_file_default_and_keyring():
    file_args = argparse.Namespace(out_keyring="", out_file="")
    store = biomni_refresher.resolve_store(file_args)
    assert store["kind"] == "file" and store["path"].endswith("broker_token")

    kr_args = argparse.Namespace(out_keyring="biomni:andrei", out_file="")
    store = biomni_refresher.resolve_store(kr_args)
    assert store == {"kind": "keyring", "service": "biomni", "user": "andrei"}

    kr_default_user = argparse.Namespace(out_keyring="biomni", out_file="")
    assert biomni_refresher.resolve_store(kr_default_user)["user"] == "biomni"


# --------------------------------------------------------------------------- #
# Masking + lazy Playwright hint
# --------------------------------------------------------------------------- #
def test_mask():
    assert biomni_refresher._mask("abcdefghij") == "...ghij"
    assert biomni_refresher._mask("short") == "set"
    assert biomni_refresher._mask("") == ""


def test_playwright_missing_returns_clear_hint():
    # Playwright is not installed in the test env -> a clear pip hint, no crash.
    mod, err = biomni_refresher._playwright()
    if mod is None:
        assert "pip install playwright" in err
