"""MCP CallToolResult / tool-schema shapes used by the TST-0044 suite.

This is the contract the adapter must enforce. A result that does not match
CallToolResult is malformed. Mapping a malformed payload to SUCCESS with no
id and empty content is EMPTY_SUCCESS (P1).
"""
from __future__ import annotations

from typing import Any

ALLOWED_CONTENT_TYPES = frozenset(
    {"text", "image", "resource", "resource_link", "audio"}
)


class MalformedResult(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(detail or code)


def canonical_schema(schema: Any) -> Any:
    """Stable JSON-comparable form (object key order ignored)."""
    return json_canonicalize(schema)


def json_canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [json_canonicalize(v) for v in value]
    if isinstance(value, tuple):
        return [json_canonicalize(v) for v in value]
    return value


def schemas_equal(a: Any, b: Any) -> bool:
    return json_canonicalize(a) == json_canonicalize(b)


def parse_call_tool_result(raw: Any) -> dict:
    """Raise MalformedResult unless `raw` is a CallToolResult object."""
    if raw is None:
        raise MalformedResult("null-result")
    if isinstance(raw, (bytes, bytearray)):
        raise MalformedResult("bytes-result")
    if isinstance(raw, str):
        raise MalformedResult("string-result", raw[:80])
    if not isinstance(raw, dict):
        raise MalformedResult("non-object", type(raw).__name__)
    if "content" not in raw:
        raise MalformedResult("missing-content")
    content = raw["content"]
    if not isinstance(content, list):
        raise MalformedResult("content-not-array", type(content).__name__)
    for i, item in enumerate(content):
        if not isinstance(item, dict):
            raise MalformedResult(f"content[{i}]-not-object")
        ctype = item.get("type")
        if ctype not in ALLOWED_CONTENT_TYPES:
            raise MalformedResult(f"content[{i}]-unknown-type", repr(ctype))
        if ctype == "text" and "text" not in item:
            raise MalformedResult(f"content[{i}]-text-missing-text")
        if ctype == "image" and ("data" not in item or "mimeType" not in item):
            raise MalformedResult(f"content[{i}]-image-incomplete")
    if "isError" in raw and not isinstance(raw["isError"], bool):
        raise MalformedResult("isError-not-bool")
    return raw


def namespaced(server_id: str, tool_name: str) -> str:
    if not server_id or not tool_name:
        raise ValueError("server_id and tool_name required")
    if "__" in tool_name:
        raise ValueError("bare tool name must not contain the namespace marker")
    return f"{server_id}__{tool_name}"


def split_namespaced(full: str) -> tuple[str, str]:
    if "__" not in full:
        raise ValueError(f"not namespaced: {full!r}")
    server, tool = full.split("__", 1)
    if not server or not tool:
        raise ValueError(f"empty namespace half: {full!r}")
    return server, tool
