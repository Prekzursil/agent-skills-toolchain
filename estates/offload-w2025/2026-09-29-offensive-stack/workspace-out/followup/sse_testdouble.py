#!/usr/bin/env python3
"""Burp-MCP-flavored SSE TEST DOUBLE (rpc-dispatch lane verification, 2026-09-30).

Mirrors Burp Suite's MCP extension transport: the SSE stream is served at the
ROOT path of the port (GET / streams `endpoint` events; JSON-RPC frames POST
to the endpoint returned in the event). This exists ONLY to prove the
gateway's kind=mcp-sse client transport (SSE handshake + JSON-RPC proxy)
round-trips for real; Burp itself is not installed on this box. Binds
127.0.0.1 ONLY. Kill after use.
"""
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

HOST, PORT = "127.0.0.1", 9876

mcp_server = FastMCP("burp-sse-test-double")


@mcp_server.tool()
def ping() -> str:
    """Trivial echo tool for transport verification."""
    return "pong-from-burp-sse-test-double"


@mcp_server.tool()
def get_proxy_http_history_count() -> int:
    """Stand-in for a trivial real Burp tool call."""
    return 0


sse = SseServerTransport("/message")


async def handle_sse(request: Request) -> Response:
    # same request._send conversion the installed SDK's own sse_app uses
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:  # type: ignore[reportPrivateUsage]
        await mcp_server._mcp_server.run(
            streams[0], streams[1],
            mcp_server._mcp_server.create_initialization_options())
    return Response()


app = Starlette(
    debug=True,
    routes=[
        Route("/", endpoint=handle_sse, methods=["GET"]),           # Burp flavor: SSE at root
        Mount("/message", app=sse.handle_post_message),             # raw ASGI app -> Mount
    ],
)

if __name__ == "__main__":
    print("burp SSE test double on http://%s:%d/ (root path)" % (HOST, PORT), flush=True)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
