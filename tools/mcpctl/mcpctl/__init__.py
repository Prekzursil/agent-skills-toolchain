"""mcpctl -- read-only MCP inventory + health matrix core.

Every module here is a PURE function over already-loaded data except
:mod:`mcpctl.sources`, the one thin filesystem shim (whose reader is injected, so
it is hermetically testable too). Nothing in this package writes, toggles, or
otherwise mutates any MCP configuration: live mutation is deliberately out of
scope for this unit.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
