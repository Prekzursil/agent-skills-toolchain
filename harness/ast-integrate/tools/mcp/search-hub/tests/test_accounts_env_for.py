#!/usr/bin/env python3
"""Tests for the ONE additive helper added to the shared accounts.py:
``AccountStore.env_for(platform, name)`` -- a read-only named-account resolver
the search-hub rotator uses to bind a child to any specific key."""

from __future__ import annotations

import os
import sys

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

import accounts  # noqa: E402
from accounts import AccountPolicy, AccountStore  # noqa: E402


def _store(tmp_path, environ):
    pol = AccountPolicy(
        platform="exa", mode="env", seed_env=("EXA_API_KEY",), label="Exa"
    )
    return AccountStore(str(tmp_path / "acc.json"), [pol], environ=environ)


def test_env_for_resolves_named_account(tmp_path):
    store = _store(tmp_path, {"EXA_API_KEY": "primary", "EXA_ALT": "alt"})
    store.handle("exa", "add", {"name": "alt", "env": {"EXA_API_KEY": "${EXA_ALT}"}})
    # env_for resolves a SPECIFIC account, independent of which is active.
    assert store.env_for("exa", "default") == {"EXA_API_KEY": "primary"}
    assert store.env_for("exa", "alt") == {"EXA_API_KEY": "alt"}


def test_env_for_does_not_change_active(tmp_path):
    store = _store(tmp_path, {"EXA_API_KEY": "primary", "EXA_ALT": "alt"})
    store.handle("exa", "add", {"name": "alt", "env": {"EXA_API_KEY": "${EXA_ALT}"}})
    store.env_for("exa", "alt")
    assert store.handle("exa", "current", {})["active"] == "default"  # unchanged


def test_env_for_unknown_account_is_empty(tmp_path):
    store = _store(tmp_path, {"EXA_API_KEY": "primary"})
    assert store.env_for("exa", "ghost") == {}


def test_env_for_unknown_platform_is_empty(tmp_path):
    store = _store(tmp_path, {"EXA_API_KEY": "primary"})
    assert store.env_for("nope", "default") == {}


def test_env_for_cli_mode_is_empty(tmp_path):
    cli = accounts.CliProfileSpec(
        list_cmd=("x",), current_cmd=("x",), activate_cmd=("x", "{name}")
    )
    store = AccountStore(
        str(tmp_path / "c.json"),
        [AccountPolicy(platform="azure", mode="cli", cli=cli)],
        environ={},
    )
    assert store.env_for("azure", "anything") == {}
