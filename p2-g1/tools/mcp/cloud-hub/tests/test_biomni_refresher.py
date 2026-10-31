#!/usr/bin/env python3
"""Unit tests for the Biomni refresh-at-source broker (``biomni-mcp/refresher.py``).

Covers the network/browser-free logic: Bearer extraction, best-token selection,
store writing (file + keyring), store-spec resolution, masking, and the lazy
Playwright hint. The Playwright shell needs a real browser and is integration-only.
The module is loaded by explicit path as ``biomni_refresher``."""

from __future__ import annotations

import argparse
import importlib.util
import json
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


# --------------------------------------------------------------------------- #
# gather: multi-account planning + rotation-wiring emission (no browser)
# --------------------------------------------------------------------------- #
def test_plan_accounts_increments_ports():
    plan = biomni_refresher.plan_accounts(["andrei", "marius"], base_port=8787)
    assert [a["name"] for a in plan] == ["andrei", "marius"]
    assert [a["port"] for a in plan] == [8787, 8788]
    assert plan[0]["api_base"] == "http://127.0.0.1:8787"
    assert plan[1]["profile"].endswith(os.path.join("profiles", "marius"))
    assert plan[1]["store_file"].endswith(os.path.join("tokens", "marius"))


def test_render_accounts_block_has_no_token_just_handles():
    plan = biomni_refresher.plan_accounts(["andrei", "marius"], base_port=8787)
    block = json.loads(biomni_refresher.render_accounts_block(plan))
    assert block["biomni"]["active"] == "andrei"
    envs = [a["env"] for a in block["biomni"]["accounts"]]
    assert envs[0] == {"BIOMNI_API_BASE": "http://127.0.0.1:8787", "BIOMNI_BROKER": "1"}
    assert envs[1]["BIOMNI_API_BASE"] == "http://127.0.0.1:8788"
    # No token key anywhere — only loopback handles.
    assert "BIOMNI_TOKEN" not in json.dumps(block)
    assert "BIOMNI_REFRESH_TOKEN" not in json.dumps(block)


def test_render_daemons_one_broker_and_watch_per_account():
    plan = biomni_refresher.plan_accounts(["andrei"], base_port=8790)
    lines = biomni_refresher.render_daemons(plan)
    assert len(lines) == 2
    assert (
        "broker.py --port 8790" in lines[0] and "BIOMNI_BROKER_TOKEN_FILE=" in lines[0]
    )
    assert "refresher.py watch" in lines[1] and "--profile" in lines[1]


def test_cdp_arg_plumbs_through():
    parsed = biomni_refresher.build_parser().parse_args(
        ["--cdp", "http://127.0.0.1:9222", "refresh"]
    )
    assert parsed.cdp == "http://127.0.0.1:9222"
    assert biomni_refresher.build_parser().parse_args(["refresh"]).cdp == ""


def test_cookie_name_default_is_session_id():
    assert (
        biomni_refresher.build_parser().parse_args(["refresh"]).cookie_name
        == "session_id"
    )


def test_capture_routes_cookie_when_cdp_set(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        biomni_refresher,
        "_capture_cookie",
        lambda cdp, url, name, t: seen.update(route=("cookie", name)) or ("CK", ""),
    )
    monkeypatch.setattr(
        biomni_refresher,
        "_capture_bearer",
        lambda *a, **k: seen.update(route=("bearer", None)) or ("BR", ""),
    )
    args = argparse.Namespace(
        cdp="http://127.0.0.1:9222",
        url="u",
        cookie_name="session_id",
        timeout_ms=1000,
        profile="p",
    )
    tok, _ = biomni_refresher._capture(args)
    # CDP set -> COOKIE capture (Biomni's real auth), never the dead Bearer path.
    assert tok == "CK" and seen["route"] == ("cookie", "session_id")


# --------------------------------------------------------------------------- #
# Session-validity gate: a NON-EMPTY cookie is not proof of a live session.     #
# --------------------------------------------------------------------------- #
class _FakeCtx:
    """A CDP browser context whose cookie jar can be refreshed by opening a page."""

    def __init__(self, value, on_open=None):
        self._value = value
        self._on_open = on_open
        self.pages_opened = 0

    def cookies(self, _urls):
        return [{"name": "session_id", "value": self._value}] if self._value else []

    def new_page(self):
        self.pages_opened += 1
        if self._on_open is not None:
            self._value = self._on_open()
        return _FakePage()


class _FakePage:
    def goto(self, _url, timeout=None):
        return None

    def wait_for_timeout(self, _ms):
        return None

    def close(self):
        return None


def _install_fake_cdp(monkeypatch, ctx):
    """Point ``_playwright`` at a fake ``sync_playwright`` exposing ``ctx``."""

    class _Browser:
        contexts = [ctx]

    class _P:
        class chromium:  # noqa: N801  (mirrors the playwright attribute name)
            @staticmethod
            def connect_over_cdp(_url):
                return _Browser()

    class _Sync:
        def __enter__(self):
            return _P()

        def __exit__(self, *_exc):
            return False

    monkeypatch.setattr(
        biomni_refresher, "_playwright", lambda: (lambda: _Sync(), None)
    )


def _stub_validity(monkeypatch, verdicts):
    """Serve ``verdicts`` (one per call) from ``check_session_cookie``."""
    calls = []
    seq = list(verdicts)

    def _check(value, *_a, **_k):
        calls.append(value)
        return seq.pop(0) if seq else "valid"

    monkeypatch.setattr(biomni_refresher, "check_session_cookie", _check)
    return calls


def test_revoked_cookie_is_not_reported_as_a_successful_refresh(monkeypatch):
    """A server-revoked (but non-empty) cookie must FAIL, not be stored as fresh."""
    ctx = _FakeCtx("server-revoked-cookie")
    _install_fake_cdp(monkeypatch, ctx)
    _stub_validity(monkeypatch, ["revoked", "revoked"])
    value, err = biomni_refresher._capture_cookie(
        "http://127.0.0.1:9222", "u", "session_id", 10
    )
    assert value == ""
    assert "rejected" in err.lower()
    # It must have tried to re-establish the session before giving up.
    assert ctx.pages_opened == 1


def test_revoked_cookie_is_re_established_by_opening_the_app(monkeypatch):
    """If opening the app mints a NEW accepted cookie, that one is returned."""
    ctx = _FakeCtx("server-revoked-cookie", on_open=lambda: "fresh-cookie")
    _install_fake_cdp(monkeypatch, ctx)
    seen = _stub_validity(monkeypatch, ["revoked", "valid"])
    value, err = biomni_refresher._capture_cookie(
        "http://127.0.0.1:9222", "u", "session_id", 10
    )
    assert (value, err) == ("fresh-cookie", "")
    assert seen == ["server-revoked-cookie", "fresh-cookie"]


def test_valid_cookie_is_accepted_without_opening_a_page(monkeypatch):
    ctx = _FakeCtx("live-cookie")
    _install_fake_cdp(monkeypatch, ctx)
    _stub_validity(monkeypatch, ["valid"])
    assert biomni_refresher._capture_cookie("cdp", "u", "session_id", 10) == (
        "live-cookie",
        "",
    )
    assert ctx.pages_opened == 0


def test_unknown_validity_does_not_discard_a_possibly_good_cookie(monkeypatch):
    """A transport blip / 5xx must NOT be treated as revocation."""
    ctx = _FakeCtx("maybe-good")
    _install_fake_cdp(monkeypatch, ctx)
    _stub_validity(monkeypatch, ["unknown"])
    assert biomni_refresher._capture_cookie("cdp", "u", "session_id", 10) == (
        "maybe-good",
        "",
    )
    assert ctx.pages_opened == 0


def _fake_urlopen(status=None, http_error=None, exc=None):
    class _Resp:
        def __init__(self):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def _open(_req, timeout=None):
        if exc is not None:
            raise exc
        if http_error is not None:
            raise biomni_refresher.urllib.error.HTTPError(
                "u", http_error, "err", None, None
            )
        return _Resp()

    return _open


def test_check_session_cookie_classifies_upstream_answers(monkeypatch):
    urlopen = biomni_refresher.urllib.request.urlopen
    try:
        for stub, expected in (
            (_fake_urlopen(status=200), "valid"),
            (_fake_urlopen(http_error=401), "revoked"),
            (_fake_urlopen(http_error=403), "revoked"),
            (_fake_urlopen(http_error=503), "unknown"),
            (_fake_urlopen(exc=OSError("boom")), "unknown"),
        ):
            monkeypatch.setattr(biomni_refresher.urllib.request, "urlopen", stub)
            assert biomni_refresher.check_session_cookie("v") == expected
    finally:
        monkeypatch.setattr(biomni_refresher.urllib.request, "urlopen", urlopen)
    assert biomni_refresher.check_session_cookie("") == "revoked"


def test_refresh_returns_nonzero_for_a_revoked_cookie(monkeypatch, tmp_path):
    """``cmd_refresh`` must exit 1 and write NOTHING when the session is dead."""
    store_file = tmp_path / "broker_token"
    monkeypatch.setattr(
        biomni_refresher,
        "_capture",
        lambda _args: ("", "the 'session_id' cookie ... is REJECTED"),
    )
    args = argparse.Namespace(
        cdp="cdp",
        url="u",
        cookie_name="session_id",
        timeout_ms=10,
        profile="p",
        out_file=str(store_file),
        out_keyring="",
    )
    assert biomni_refresher.cmd_refresh(args) == 1
    assert not store_file.exists()


def test_capture_routes_bearer_without_cdp(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        biomni_refresher,
        "_capture_bearer",
        lambda *a, **k: seen.update(route="bearer") or ("BR", ""),
    )
    args = argparse.Namespace(
        cdp="", url="u", cookie_name="session_id", timeout_ms=1000, profile="p"
    )
    tok, _ = biomni_refresher._capture(args)
    assert tok == "BR" and seen["route"] == "bearer"
