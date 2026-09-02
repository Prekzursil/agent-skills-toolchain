"""In-process mock MCP servers used as mounted adapters under test.

Live estate MCP binaries are not spawned. Each mock advertises a frozen
tool schema and can return a well-formed or injected-malformed tools/call
result. That is the injection seam the evidence requirement names.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

ECHO_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}
INSPECT_SCHEMA = {
    "type": "object",
    "properties": {"path": {"type": "string"}},
    "required": ["path"],
    "additionalProperties": False,
}

# Injections the evidence requirement demands: one malformed payload per
# adapter. The suite runs the full set against every adapter.
MALFORMED_INJECTIONS: list[tuple[str, Any]] = [
    ("null-result", None),
    ("empty-object", {}),
    ("missing-content", {"isError": False}),
    ("content-not-array", {"content": "ok", "isError": False}),
    ("content-item-not-object", {"content": ["x"], "isError": False}),
    ("text-missing-text", {"content": [{"type": "text"}], "isError": False}),
    ("unknown-content-type", {"content": [{"type": "prompt"}], "isError": False}),
    ("isError-not-bool", {"content": [{"type": "text", "text": "x"}], "isError": "no"}),
    ("string-result", "SUCCESS"),
    ("bytes-result", b"{}"),
]


class MockServer:
    """One mounted MCP server. `call_raw` is the tools/call result before
    the adapter classifies it."""

    def __init__(
        self,
        server_id: str,
        *,
        transport: str,
        tools: list[dict],
        handler: Callable[[str, dict], Any] | None = None,
    ) -> None:
        self.server_id = server_id
        self.transport = transport
        self._tools = deepcopy(tools)
        self._handler = handler or self._default_handler
        self.spawned = False
        self.inject: tuple[str, Any] | None = None

    def advertised_tools(self) -> list[dict]:
        return deepcopy(self._tools)

    def start(self) -> None:
        self.spawned = True

    def reap(self) -> None:
        self.spawned = False

    def list_tools(self) -> list[dict]:
        if not self.spawned:
            raise RuntimeError(f"{self.server_id} not started")
        return self.advertised_tools()

    def call_raw(self, tool_name: str, arguments: dict) -> Any:
        if not self.spawned:
            raise RuntimeError(f"{self.server_id} not started")
        if self.inject is not None:
            return deepcopy(self.inject[1]) if not isinstance(self.inject[1], (bytes, bytearray)) else self.inject[1]
        return self._handler(tool_name, arguments or {})

    def _default_handler(self, tool_name: str, arguments: dict) -> dict:
        if tool_name == "echo":
            text = str(arguments.get("text", ""))
            return {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            }
        if tool_name == "inspect":
            path = str(arguments.get("path", ""))
            return {
                "content": [{"type": "text", "text": f"inspect:{path}"}],
                "isError": False,
            }
        return {
            "content": [{"type": "text", "text": f"unknown tool {tool_name}"}],
            "isError": True,
        }


def alpha_stdio() -> MockServer:
    return MockServer(
        "alpha",
        transport="stdio",
        tools=[
            {
                "name": "echo",
                "description": "Echo text back as a tool result",
                "inputSchema": deepcopy(ECHO_SCHEMA),
            }
        ],
    )


def beta_http() -> MockServer:
    return MockServer(
        "beta",
        transport="http",
        tools=[
            {
                "name": "echo",
                "description": "Echo text (beta copy; name collides with alpha)",
                "inputSchema": deepcopy(ECHO_SCHEMA),
            },
            {
                "name": "inspect",
                "description": "Inspect a path",
                "inputSchema": deepcopy(INSPECT_SCHEMA),
            },
        ],
    )


def fixture_pair() -> list[MockServer]:
    return [alpha_stdio(), beta_http()]
