#!/usr/bin/env python3
"""Smoke test: the FastMCP server imports and registers the four fleet tools."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp.server.fastmcp")

import server  # noqa: E402


def test_server_registers_the_four_tools():
    assert server.mcp.name == "codex-fleet-github"
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "fleet_dispatch",
        "fleet_sweep",
        "fleet_status",
        "fleet_orchestrate",
    }


def test_dispatch_tool_validates_and_reports_error():
    # bad repo -> FleetError is caught and returned as a structured failure
    out = server.fleet_dispatch("not-a-repo", "do it")
    assert out["ok"] is False
    assert "invalid repo" in out["error"]
