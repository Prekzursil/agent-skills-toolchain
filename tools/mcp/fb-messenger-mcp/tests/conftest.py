"""Shared pytest fixtures. Adds the repo root to sys.path so `import fbmcp`
works no matter where pytest is invoked from."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fbmcp import build_server  # noqa: E402


@pytest.fixture(scope="session")
def mcp_server():
    return build_server()


@pytest.fixture
def get_tool(mcp_server):
    """Return the raw async function backing a registered MCP tool by name."""

    def _get(name: str):
        return mcp_server._tool_manager.get_tool(name).fn

    return _get
