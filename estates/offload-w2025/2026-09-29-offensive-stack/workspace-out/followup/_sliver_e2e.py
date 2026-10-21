#!/usr/bin/env python3
"""finish-limits lane 2026-09-30: REAL sliver end-to-end through the gateway.
Requires: sliver-server daemon up on 127.0.0.1:31337 + operator config in
~/.sliver-client/configs (both stood up this lane).
1) harness_invoke('sliver','__list__') must return the REAL tool list.
2) one trivial real tool call must round-trip (list_sessions - an RPC to the
   live sliver-server, expected: empty-but-real result, no sessions yet)."""
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
            caps = json.loads((await s.call_tool("harness_capabilities", {})).content[0].text)
            row = {b["name"]: b for b in caps["backends"]}["sliver"]
            print("[sliver row] status=%s" % row["status"])
            print("    detail: %s" % row["detail"][:250])
            if row["status"] != "available":
                fails.append("sliver row not available")

            tools_raw = (await s.call_tool(
                "harness_invoke",
                {"backend": "sliver", "tool": "__list__"})).content[0].text
            print("\n[harness_invoke sliver __list__] raw:")
            print(tools_raw[:2000])
            tools = json.loads(tools_raw)
            tlist = tools.get("tools") or tools.get("result", {}).get("tools")
            if not tlist:
                fails.append("__list__ returned no tools")
            else:
                names = [t if isinstance(t, str) else t.get("name") for t in tlist]
                print("\ntool count: %d" % len(names))
                print("tool names: %s" % names)

            call_raw = (await s.call_tool(
                "harness_invoke",
                {"backend": "sliver", "tool": "list_sessions_and_beacons",
                 "arguments": "{}"})).content[0].text
            print("\n[harness_invoke sliver list_sessions] raw:")
            print(call_raw[:1500])
            call = json.loads(call_raw)
            if not call.get("ok"):
                fails.append("list_sessions call not ok: %s" % call_raw[:300])
    print("\nSLIVER-E2E RESULT:", "PASS" if not fails else "FAIL %s" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
