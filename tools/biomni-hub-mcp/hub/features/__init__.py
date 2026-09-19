"""biomni-hub Component A3 -- expanded ("drive it better") feature tools.

Additive FastMCP tools the hub exposes on top of the canonical 10-tool surface:

  * ``biomni_run_history``   (run_history.py)  -- cross-backend task history
  * ``biomni_fetch_artifact``(fetch_artifact.py)-- real result-file download
  * ``biomni_cost``          (cost.py)          -- per-run + rolling cost meter
  * ``biomni_tool_catalog``  (tool_catalog.py)  -- introspect ~150 Biomni tools
  * ``biomni_inject_mcp``    (inject_mcp.py)    -- inject a fleet MCP (add_mcp)

plus the SQLite run-history/artifacts store (store.py) that backs them.

The hub wires these in with::

    from features import register_all
    from features.context import HubContext, build_default_context
    ctx = build_default_context()          # then populate ctx.backends
    register_all(mcp, ctx)                  # mcp is the hub's FastMCP instance
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import cost, fetch_artifact, inject_mcp, run_history, tool_catalog
from .bridge import BiomniBackendClient, bridge_adapter
from .context import HubContext, build_default_context, default_data_dir

if TYPE_CHECKING:
    from fastmcp import FastMCP

__all__ = [
    "BiomniBackendClient",
    "HubContext",
    "bridge_adapter",
    "build_default_context",
    "default_data_dir",
    "register_all",
]

_FEATURE_MODULES = (run_history, fetch_artifact, cost, tool_catalog, inject_mcp)


def register_all(mcp: FastMCP, ctx: HubContext) -> list[str]:
    """Register every A3 feature tool on ``mcp``. Returns the tool names added."""
    for module in _FEATURE_MODULES:
        module.register(mcp, ctx)
    return [
        "biomni_run_history",
        "biomni_fetch_artifact",
        "biomni_cost",
        "biomni_tool_catalog",
        "biomni_inject_mcp",
    ]
