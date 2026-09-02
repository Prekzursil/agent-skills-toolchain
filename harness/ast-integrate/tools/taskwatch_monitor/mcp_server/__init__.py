"""MCP server surface for taskwatch_monitor.

Exposes the SAME core engine the CLI drives (registry + snapshot) over the
Model Context Protocol so an agent host can register tasks, poll status, list
the registry, attach a live watch, and set notify channels programmatically.

The sub-package is named ``mcp_server`` — never ``mcp`` — so it can import the
upstream ``mcp`` SDK (``from mcp.server.fastmcp import FastMCP``) without
shadowing it. Spec tool names use dots (``register_task`` maps 1:1 to the MCP
tool ``register_task``); the split mirrors ``scholarly-access-mcp``:

* :mod:`mcp_server.logic` — pure orchestration over ``core``/``cli`` (100 %
  branch-covered against temp registries and injected snapshots).
* :mod:`mcp_server.server` — thin FastMCP wrappers that delegate to ``logic``
  (covered by mocking ``logic``, exactly like the scholarly-access template).
"""

from __future__ import annotations

from . import logic

__all__ = ["logic"]
