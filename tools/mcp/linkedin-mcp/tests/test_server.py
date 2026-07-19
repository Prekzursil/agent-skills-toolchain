#!/usr/bin/env python3
"""Smoke test: the FastMCP server imports and registers the LinkedIn tools.

Also asserts the guard turns a missing-credential LinkedInError into a clean
structured result (never a raised exception / stack trace).
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp.server.fastmcp")

import linkedin_core as core  # noqa: E402
import server  # noqa: E402

EXPECTED_TOOLS = {
    "linkedin_auth_status",
    "linkedin_whoami",
    "linkedin_post_text",
    "linkedin_post_article",
    "linkedin_post_image",
    "linkedin_delete_post",
    "linkedin_comment",
    "linkedin_react",
    "linkedin_authorization_url",
    "linkedin_exchange_code",
    "linkedin_token_status",
}


def test_server_registers_expected_tools():
    assert server.mcp.name == "linkedin"
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == EXPECTED_TOOLS


def test_guard_converts_linkedin_error_to_structured():
    def boom():
        raise core.LinkedInError("no token")

    out = server._guard(boom)
    assert out == {"ok": False, "error": "no token"}


def test_guard_passes_through_success():
    out = server._guard(lambda: {"ok": True, "x": 1})
    assert out == {"ok": True, "x": 1}


def test_auth_status_tool_safe_with_no_credentials(monkeypatch):
    # A completely unconfigured environment must yield a clean actionable dict,
    # not a stack trace -- this is the "server always starts + lists tools" proof.
    monkeypatch.setattr(core.os, "environ", {})
    out = server.linkedin_auth_status()
    assert out["ok"] is False
    assert "LINKEDIN_ACCESS_TOKEN" in out["error"]


def test_post_text_tool_missing_token_is_clean(monkeypatch):
    monkeypatch.setattr(core.os, "environ", {})
    out = server.linkedin_post_text("hello")
    assert out["ok"] is False
    assert "LINKEDIN_ACCESS_TOKEN" in out["error"]


# --- every wrapper delegates to its core function (covers all tool bodies) --- #
def test_all_wrappers_delegate(monkeypatch):
    sentinel = {"ok": True, "sentinel": True}
    for core_fn in (
        "whoami",
        "post_text",
        "post_article",
        "post_image",
        "delete_post",
        "comment",
        "react",
        "build_authorization_url",
        "exchange_code",
        "token_status",
        "auth_status",
    ):
        monkeypatch.setattr(core, core_fn, lambda *a, **k: sentinel)

    assert server.linkedin_whoami() is sentinel
    assert server.linkedin_post_text("t") is sentinel
    assert server.linkedin_post_article("t", "https://x.com") is sentinel
    assert server.linkedin_post_image("t", "p.png") is sentinel
    assert server.linkedin_delete_post("urn:li:ugcPost:1") is sentinel
    assert server.linkedin_comment("urn:li:ugcPost:1", "hi") is sentinel
    assert server.linkedin_react("urn:li:ugcPost:1") is sentinel
    assert server.linkedin_authorization_url() is sentinel
    assert server.linkedin_exchange_code("c") is sentinel
    assert server.linkedin_token_status() is sentinel
    assert server.linkedin_auth_status() is sentinel
