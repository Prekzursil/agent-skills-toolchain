"""transport_port — the single injectable I/O boundary seam (WU-0b).

Every network/MCP read funnels through ``fetch_json(source, key) -> dict``.
Production wraps ``mcp__tooluniverse__execute_tool``; tests inject
:class:`FakeTransport`. The Protocol is preserved exactly so coverage is
structurally reachable (tests mock the port, not requests/MCP).
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable


class TransportError(RuntimeError):
    """Raised on any transport-layer failure (HTTP error, timeout, MCP down)."""


@runtime_checkable
class TransportPort(Protocol):
    """The single injectable I/O boundary."""

    def fetch_json(self, source: str, key: str) -> dict: ...


def fetch_json(port: TransportPort, source: str, key: str) -> dict:
    """Module-level convenience that delegates to a port (the seam)."""
    return port.fetch_json(source, key)


class FakeTransport:
    """Test double returning canned per-source JSON or raising seeded errors.

    ``responses`` maps ``(source, key)`` to either a dict (returned) or a
    ``TransportError`` instance (raised) — the error/timeout fixtures for G.
    """

    def __init__(self, responses: dict[tuple[str, str], object]):
        self._responses = dict(responses)
        self.calls: list[tuple[str, str]] = []

    def fetch_json(self, source: str, key: str) -> dict:
        self.calls.append((source, key))
        if (source, key) not in self._responses:
            raise TransportError(f"no canned response for {source!r}/{key!r}")
        result = self._responses[(source, key)]
        if isinstance(result, TransportError):
            raise result
        return result  # type: ignore[return-value]


class ToolUniverseTransport:
    """Thin production adapter over ``mcp__tooluniverse__execute_tool``.

    ``executor`` is the injected MCP call ``(tool_name, arguments) -> dict``.
    When no live MCP executor is supplied it raises ``NotImplementedError`` so
    Phase-0 never silently no-ops; tests inject a fake executor for coverage.
    """

    TOOL_NAME = "execute_tool"

    def __init__(self, executor: Callable[[str, dict], dict] | None = None):
        self._executor = executor

    def fetch_json(self, source: str, key: str) -> dict:
        if self._executor is None:
            raise NotImplementedError(
                "no live ToolUniverse executor wired; inject one or use FakeTransport"
            )
        try:
            return self._executor(self.TOOL_NAME, {"source": source, "key": key})
        except Exception as exc:  # wrap any MCP failure as a transport error
            raise TransportError(f"ToolUniverse execute_tool failed: {exc}") from exc
