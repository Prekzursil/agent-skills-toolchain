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
    assert len(names) == 21
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
    ):
        assert name in names


def test_token_absent_returns_clear_hint(monkeypatch):
    monkeypatch.delenv("BIOMNI_TOKEN", raising=False)
    out = json.loads(biomni_server.bm_list_projects())
    assert out["ok"] is False
    assert "BIOMNI_TOKEN not set" in out["error"]


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
