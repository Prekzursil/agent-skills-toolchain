#!/usr/bin/env python3
"""Unit tests for the built Biomni FastMCP wrapper (``biomni-mcp/server.py``).

No live api.phylo.bio: auth is read lazily so ``tools/list`` enumerates offline,
and the single network seam ``_api`` is monkeypatched to exercise routing,
effort-alias mapping, skill attachment, guardrails, and the raw passthrough. The
module is loaded by explicit path as ``biomni_server`` so it never collides with
the other built wrappers' ``server.py`` modules."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

_SERVER_PATH = os.path.join(HUB_DIR, "biomni-mcp", "server.py")
_spec = importlib.util.spec_from_file_location("biomni_server", _SERVER_PATH)
biomni_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(biomni_server)


def _fake_api(capture: dict, status: int = 200, payload=None):
    """Build a fake ``_api`` that records the call and returns (status, payload)."""

    def _api(method, path, body=None, query=None, token="", timeout=None):
        capture.update(method=method, path=path, body=body, query=query, token=token)
        return status, ({"echo": True} if payload is None else payload)

    return _api


# --------------------------------------------------------------------------- #
# Offline enumeration (no token, no network)
# --------------------------------------------------------------------------- #
def test_enumerates_full_biomni_surface_offline():
    tools = asyncio.run(biomni_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert len(names) == 25
    assert all(n.startswith("bm_") for n in names)
    for name in (
        "bm_create_session",
        "bm_send_message",
        "bm_start_processing",
        "bm_list_model_profiles",
        "bm_list_skills",
        "bm_set_skill_status",
        "bm_session_runtime",
        "bm_billing_balance",
        "bm_api_raw",
        "bm_auth_login",
        "bm_auth_poll",
        "bm_auth_status",
        "bm_auth_logout",
    ):
        assert name in names


def test_no_credentials_returns_clear_hint(monkeypatch):
    monkeypatch.delenv("BIOMNI_TOKEN", raising=False)
    monkeypatch.delenv("BIOMNI_REFRESH_TOKEN", raising=False)
    monkeypatch.setattr(biomni_server, "_load_state", lambda: {})
    biomni_server._token_cache.clear()
    out = json.loads(biomni_server.bm_list_projects())
    assert out["ok"] is False
    assert "No Biomni credentials" in out["error"]


# --------------------------------------------------------------------------- #
# Routing + serialization against a fake ``_api``
# --------------------------------------------------------------------------- #
def test_create_session_maps_effort_alias_and_body(monkeypatch):
    seen: dict = {}
    monkeypatch.setenv("BIOMNI_TOKEN", "tok-123")
    monkeypatch.setattr(
        biomni_server, "_api", _fake_api(seen, payload={"session_id": "sess_1"})
    )
    out = json.loads(
        biomni_server.bm_create_session("proj_9", "hello", model_profile="max")
    )
    assert out["ok"] and out["data"] == {"session_id": "sess_1"}
    assert seen["method"] == "POST"
    assert seen["path"] == "/v2/agent/sessions/create"
    # "max" is a friendly alias mapped to the real profile id "premium".
    assert seen["body"]["model_profile"] == "premium"
    assert seen["body"]["project_id"] == "proj_9"
    assert seen["body"]["submit_initial_message"] is True
    assert seen["token"] == "tok-123"


def test_send_message_attaches_skills(monkeypatch):
    seen: dict = {}
    monkeypatch.setenv("BIOMNI_TOKEN", "t")
    monkeypatch.setattr(biomni_server, "_api", _fake_api(seen))
    skills = '[{"id": "skill_a", "name": "celegans-rnai", "intent": "use"}]'
    out = json.loads(biomni_server.bm_send_message("sess_1", "@Addgene run it", skills))
    assert out["ok"]
    assert seen["path"] == "/v2/agent/sess_1/user_message"
    assert seen["body"]["content"] == "@Addgene run it"
    assert seen["body"]["attached_skills"][0]["id"] == "skill_a"


def test_send_message_rejects_bad_skills_json(monkeypatch):
    monkeypatch.setenv("BIOMNI_TOKEN", "t")
    out = json.loads(biomni_server.bm_send_message("sess_1", "hi", "not-json"))
    assert out["ok"] is False and "not valid JSON" in out["error"]


def test_session_runtime_validates_kind(monkeypatch):
    monkeypatch.setenv("BIOMNI_TOKEN", "t")
    # An unknown kind never reaches the network.
    out = json.loads(biomni_server.bm_session_runtime("sess_1", "bogus"))
    assert out["ok"] is False and "kind must be one of" in out["error"]


def test_session_runtime_routes_valid_kind(monkeypatch):
    seen: dict = {}
    monkeypatch.setenv("BIOMNI_TOKEN", "t")
    monkeypatch.setattr(biomni_server, "_api", _fake_api(seen, payload=[]))
    out = json.loads(biomni_server.bm_session_runtime("sess_1", "gpu-sandboxes"))
    assert out["ok"]
    assert seen["path"] == "/v2/agent/sess_1/gpu-sandboxes"
    assert seen["method"] == "GET"


def test_set_skill_status_validates(monkeypatch):
    monkeypatch.setenv("BIOMNI_TOKEN", "t")
    out = json.loads(biomni_server.bm_set_skill_status("skill_a", "on"))
    assert out["ok"] is False and "active" in out["error"]


def test_billing_uses_root_path_not_v2(monkeypatch):
    seen: dict = {}
    monkeypatch.setenv("BIOMNI_TOKEN", "t")
    monkeypatch.setattr(biomni_server, "_api", _fake_api(seen, payload={"credits": 5}))
    out = json.loads(biomni_server.bm_billing_balance())
    assert out["ok"] and out["data"] == {"credits": 5}
    # Billing lives at the root, NOT under /v2 (per the reverse-engineered surface).
    assert seen["path"] == "/billing/balance"


def test_api_raw_passthrough(monkeypatch):
    seen: dict = {}
    monkeypatch.setenv("BIOMNI_TOKEN", "t")
    monkeypatch.setattr(biomni_server, "_api", _fake_api(seen))
    out = json.loads(
        biomni_server.bm_api_raw("get", "/v2/mcp/servers", "", '{"limit": 5}')
    )
    assert out["ok"] and out["data"] == {"echo": True}
    assert seen["method"] == "get" and seen["path"] == "/v2/mcp/servers"
    assert seen["query"] == {"limit": 5} and seen["body"] is None


def test_api_raw_requires_absolute_path(monkeypatch):
    monkeypatch.setenv("BIOMNI_TOKEN", "t")
    out = json.loads(biomni_server.bm_api_raw("GET", "v2/projects"))
    assert out["ok"] is False and "absolute API path" in out["error"]


def test_401_returns_refresh_hint(monkeypatch):
    seen: dict = {}
    monkeypatch.setenv("BIOMNI_TOKEN", "expired")
    monkeypatch.setattr(
        biomni_server, "_api", _fake_api(seen, status=401, payload={"error": "nope"})
    )
    out = json.loads(biomni_server.bm_whoami())
    assert out["ok"] is False and out["status"] == 401
    assert "expired or invalid" in out["error"]


# --------------------------------------------------------------------------- #
# OAuth device-code + auto-refresh (monkeypatch the ``_oauth_post`` seam)
# --------------------------------------------------------------------------- #
def _fake_oauth(capture: dict, status: int = 200, payload=None):
    """Build a fake ``_oauth_post`` recording (endpoint, form) -> (status, payload)."""

    def _oauth_post(endpoint, form):
        capture.update(endpoint=endpoint, form=form)
        return status, (payload or {})

    return _oauth_post


def test_refresh_token_env_mints_access_token(monkeypatch):
    api_seen: dict = {}
    monkeypatch.delenv("BIOMNI_TOKEN", raising=False)
    monkeypatch.setenv("BIOMNI_REFRESH_TOKEN", "rt-1")
    biomni_server._token_cache.clear()
    monkeypatch.setattr(
        biomni_server,
        "_oauth_post",
        _fake_oauth({}, payload={"access_token": "at-fresh", "expires_in": 3600}),
    )
    monkeypatch.setattr(biomni_server, "_api", _fake_api(api_seen, payload={}))
    out = json.loads(biomni_server.bm_list_projects())
    # The env refresh token was exchanged and the MINTED access token is the bearer.
    assert out["ok"]
    assert api_seen["token"] == "at-fresh"


def test_refresh_failure_surfaces_login_hint(monkeypatch):
    monkeypatch.delenv("BIOMNI_TOKEN", raising=False)
    monkeypatch.setenv("BIOMNI_REFRESH_TOKEN", "rt-bad")
    biomni_server._token_cache.clear()
    monkeypatch.setattr(
        biomni_server,
        "_oauth_post",
        _fake_oauth({}, status=400, payload={"error": "invalid_grant"}),
    )
    out = json.loads(biomni_server.bm_list_projects())
    assert out["ok"] is False
    assert "refresh failed" in out["error"] and "bm_auth_login" in out["error"]


def test_refresh_from_state_persists_rotation(monkeypatch):
    api_seen: dict = {}
    saved: dict = {}
    monkeypatch.delenv("BIOMNI_TOKEN", raising=False)
    monkeypatch.delenv("BIOMNI_REFRESH_TOKEN", raising=False)
    biomni_server._token_cache.clear()
    monkeypatch.setattr(biomni_server, "_load_state", lambda: {"refresh_token": "old"})
    monkeypatch.setattr(biomni_server, "_save_state", lambda s: saved.update(s))
    monkeypatch.setattr(
        biomni_server,
        "_oauth_post",
        _fake_oauth(
            {},
            payload={
                "access_token": "at-2",
                "refresh_token": "new-rt",
                "expires_in": 3600,
            },
        ),
    )
    monkeypatch.setattr(biomni_server, "_api", _fake_api(api_seen, payload={}))
    out = json.loads(biomni_server.bm_whoami())
    assert out["ok"] and api_seen["token"] == "at-2"
    # A rotated refresh token from the state-file source is persisted back.
    assert saved.get("refresh_token") == "new-rt"


def test_auth_login_returns_user_code(monkeypatch):
    seen: dict = {}
    biomni_server._pending_device.clear()
    monkeypatch.setattr(
        biomni_server,
        "_oauth_post",
        _fake_oauth(
            seen,
            payload={
                "device_code": "dev-1",
                "user_code": "WXYZ-1234",
                "verification_uri": "https://signin.phylo.bio/device",
                "verification_uri_complete": "https://signin.phylo.bio/device?code=WXYZ-1234",
                "interval": 5,
                "expires_in": 600,
            },
        ),
    )
    out = json.loads(biomni_server.bm_auth_login())
    assert out["ok"] and out["user_code"] == "WXYZ-1234"
    assert "verification_uri_complete" in out
    assert seen["endpoint"].endswith("/oauth2/device_authorization")
    assert biomni_server._pending_device["device_code"] == "dev-1"


def test_auth_poll_success_saves_and_masks(monkeypatch):
    saved: dict = {}
    biomni_server._pending_device.clear()
    biomni_server._pending_device.update(
        device_code="dev-1", interval=1.0, expires_at=biomni_server.time.time() + 600
    )
    monkeypatch.setattr(biomni_server, "_load_state", lambda: {})
    monkeypatch.setattr(biomni_server, "_save_state", lambda s: saved.update(s))
    monkeypatch.setattr(biomni_server, "_state_path", lambda: "/tmp/biomni-token.json")
    monkeypatch.setattr(
        biomni_server,
        "_oauth_post",
        _fake_oauth(
            {},
            payload={"access_token": "at", "refresh_token": "rt", "expires_in": 3600},
        ),
    )
    raw = biomni_server.bm_auth_poll(max_wait_seconds=0)
    out = json.loads(raw)
    assert out["ok"] and out["authenticated"] and out["has_refresh_token"]
    assert saved.get("refresh_token") == "rt"
    # The raw token values must NEVER appear in the tool output.
    assert '"rt"' not in raw and '"at"' not in raw
    assert not biomni_server._pending_device  # cleared on success


def test_auth_poll_pending_when_not_yet_approved(monkeypatch):
    biomni_server._pending_device.clear()
    biomni_server._pending_device.update(
        device_code="dev-1", interval=1.0, expires_at=biomni_server.time.time() + 600
    )
    monkeypatch.setattr(
        biomni_server,
        "_oauth_post",
        _fake_oauth({}, status=400, payload={"error": "authorization_pending"}),
    )
    out = json.loads(biomni_server.bm_auth_poll(max_wait_seconds=0))
    assert out["ok"] is False and out["pending"] is True
    assert out["error"] == "authorization_pending"


def test_auth_poll_without_login_errors(monkeypatch):
    biomni_server._pending_device.clear()
    out = json.loads(biomni_server.bm_auth_poll())
    assert out["ok"] is False and "no pending login" in out["error"]


def test_auth_status_masks_token(monkeypatch):
    monkeypatch.delenv("BIOMNI_TOKEN", raising=False)
    monkeypatch.setenv("BIOMNI_REFRESH_TOKEN", "rt-1")
    monkeypatch.setattr(biomni_server, "_load_state", lambda: {})
    biomni_server._token_cache.clear()
    biomni_server._token_cache.update(
        access_token="supersecrettoken", expires_at=biomni_server.time.time() + 100
    )
    out = json.loads(biomni_server.bm_auth_status())
    assert out["auth_source"] == "BIOMNI_REFRESH_TOKEN (env)"
    # Masked preview only -- the full token is never exposed.
    assert out["cached_access_token"] == "...oken"
    assert "supersecrettoken" not in json.dumps(out)


def test_auth_logout_clears(tmp_path, monkeypatch):
    state_file = tmp_path / "token.json"
    state_file.write_text('{"refresh_token": "rt"}', encoding="utf-8")
    monkeypatch.setattr(biomni_server, "_state_path", lambda: str(state_file))
    biomni_server._token_cache.update(access_token="x", expires_at=1.0)
    out = json.loads(biomni_server.bm_auth_logout())
    assert out["ok"] and out["cleared_state_file"] is True
    assert not state_file.exists()
    assert not biomni_server._token_cache


# --------------------------------------------------------------------------- #
# Broker mode (a local token-broker fronts the API; the connector holds no token)
# --------------------------------------------------------------------------- #
def test_broker_mode_returns_sentinel_and_needs_no_token(monkeypatch):
    seen: dict = {}
    monkeypatch.delenv("BIOMNI_TOKEN", raising=False)
    monkeypatch.delenv("BIOMNI_REFRESH_TOKEN", raising=False)
    monkeypatch.setenv("BIOMNI_BROKER", "1")
    biomni_server._token_cache.clear()
    tok, err = biomni_server._token()
    assert tok == "broker" and err == ""
    # A tool call proceeds with the sentinel; the local broker injects the real Bearer.
    monkeypatch.setattr(biomni_server, "_api", _fake_api(seen, payload={"p": []}))
    out = json.loads(biomni_server.bm_list_projects())
    assert out["ok"] and seen["token"] == "broker"
