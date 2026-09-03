#!/usr/bin/env python3
"""Cursor MCP tool for GLM 5.3 through Hugging Face's official router."""

from __future__ import annotations

import glm53_core as core
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("glm53-space", version="0.1.0")


@mcp.tool()
def glm53_chat(user_prompt: str, system_prompt: str = "") -> dict[str, object]:
    """Ask GLM 5.3 a text question.

    ``system_prompt`` is deliberately optional and blank by default so callers
    can supply any system instruction per invocation. Hugging Face's official
    inference router receives both fields; do not send secrets or private source
    material.
    """
    try:
        response = core.invoke(user_prompt, system_prompt)
    except core.Glm53Error as exc:
        raise ToolError(str(exc)) from None
    return {
        "ok": True,
        "model": core.MODEL_ID,
        "upstream_model": core.HF_MODEL_ID,
        "trust": "untrusted-third-party-model-output",
        "response": (
            "<untrusted-model-output>"
            f"{response}"
            "</untrusted-model-output>"
        ),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
