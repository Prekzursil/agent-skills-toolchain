#!/usr/bin/env python3
"""Phase-2 negative test (rpc-dispatch lane 2026-09-30): doubles are dead;
after the probe TTL the converted rows must flip to unavailable with the REAL
transport error (not a stub message, not a stale 'available')."""
import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

GATEWAY = "http://127.0.0.1:31100/mcp"


async def main() -> int:
    fails = []
    async with streamablehttp_client(GATEWAY) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            status = json.loads((await s.call_tool("harness_bridge_status", {})).content[0].text)
            rows = {b["name"]: b for b in status["backends"]}
            for name in ("metasploit", "burp"):
                b = rows[name]
                print(f"[{name}] status={b['status']}")
                print(f"    detail: {b['detail'][:240]}")
                if b["status"] != "unavailable":
                    fails.append(f"{name} did not flip to unavailable")
            # invoke against the now-dead burp endpoint: error propagation check
            raw = (await s.call_tool("harness_invoke", {
                "backend": "burp", "tool": "ping", "arguments": "{}"})).content[0].text
            print("--- burp.ping raw response after server stop:")
            print(raw[:600])
            out = json.loads(raw)
            if "error" not in out or "stub" in json.dumps(out).lower():
                fails.append("burp invoke did not surface a real transport error")
            if "unavailable" not in out.get("error", ""):
                fails.append("burp invoke error shape unexpected")
    print("\nPHASE-2 RESULT:", "PASS" if not fails else f"FAIL {fails}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
