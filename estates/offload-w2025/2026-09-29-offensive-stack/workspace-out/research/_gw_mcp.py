#!/usr/bin/env python3
"""Probe estate MCP gateway (127.0.0.1:31100) for a usable firecrawl tool via JSON-RPC streamable HTTP."""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:31100/mcp"


def rpc(method, params, session=None, notify=False):
    body = {"jsonrpc": "2.0", "method": method, "params": params}
    if not notify:
        body["id"] = 1
    req = urllib.request.Request(
        BASE, data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **({"mcp-session-id": session} if session else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            sid = r.headers.get("mcp-session-id")
            raw = r.read().decode()
            # streamable http may return SSE frames
            if raw.startswith("event:") or raw.startswith("data:"):
                for line in raw.splitlines():
                    if line.startswith("data:"):
                        raw = line[5:].strip()
                        break
            return sid, json.loads(raw) if raw else None
    except Exception as e:
        return None, f"ERR {type(e).__name__}: {e}"


sid, init = rpc("initialize", {
    "protocolVersion": "2025-03-26",
    "capabilities": {},
    "clientInfo": {"name": "agent-memory-lane", "version": "1.0"},
})
print("init:", json.dumps(init)[:200] if init else init, "sid:", sid)
if sid is None:
    sys.exit(1)
rpc("notifications/initialized", {}, sid, notify=True)
sid2, tools = rpc("tools/list", {}, sid)
if isinstance(tools, dict):
    names = [t["name"] for t in tools.get("result", {}).get("tools", [])]
    print(len(names), "tools")
    fc = [n for n in names if "fire" in n.lower() or "crawl" in n.lower() or "scrape" in n.lower()]
    print("firecrawl-ish tools:", fc)
    if fc:
        t = fc[0]
        sid3, res = rpc("tools/call", {"name": t, "arguments": {"query": "Graphiti LadybugDB agent memory MCP", "limit": 5}}, sid)
        print("call result:", json.dumps(res)[:1500])
else:
    print("tools/list failed:", tools)
