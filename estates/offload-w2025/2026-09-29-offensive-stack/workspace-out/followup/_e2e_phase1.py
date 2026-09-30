#!/usr/bin/env python3
"""End-to-end rpc-dispatch lane verification (2026-09-30), through the live
gateway at 127.0.0.1:31100/mcp. Phase 1: with test doubles up - real invokes.
Phase 2 is run separately after the doubles are killed (negative flip test).
"""
import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

GATEWAY = "http://127.0.0.1:31100/mcp"


async def call(s, tool, args):
    res = await s.call_tool(tool, args)
    return res.content[0].text


async def main() -> int:
    fails = []
    async with streamablehttp_client(GATEWAY) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()

            # ---- 1. status of every converted/reclassified row ----
            print("=== harness_bridge_status (converted rows) ===")
            raw = await call(s, "harness_bridge_status", {})
            status = json.loads(raw)
            wanted = ["metasploit", "sliver", "burp", "ghidra", "ida", "jadx",
                      "caldera", "havoc", "mythic"]
            rows = {b["name"]: b for b in status["backends"]}
            for name in wanted:
                b = rows[name]
                print(f"[{name}] kind={b['kind']} status={b['status']}")
                print(f"    detail: {b['detail'][:220]}")

            # ---- 2. real invokes, raw responses recorded ----
            print("\n=== real harness_invoke calls (raw responses) ===")
            cases = [
                ("metasploit", "core.version", {}),
                ("metasploit", "core.stats", {}),
                ("burp", "ping", {}),
                ("ghidra", "list_segments", {"offset": 0, "limit": 5}),
                ("sliver", "list_sessions", {}),
            ]
            for backend, tool, args in cases:
                raw = await call(s, "harness_invoke", {
                    "backend": backend, "tool": tool,
                    "arguments": json.dumps(args)})
                print(f"--- {backend}.{tool} raw response:")
                print(raw[:900])

            # ---- 3. honesty assertions ----
            caps = json.loads(await call(s, "harness_capabilities", {}))
            rows2 = {b["name"]: b for b in caps["backends"]}
            rpc_rows = [n for n, b in rows2.items() if b["kind"] == "rpc"]
            print("\n=== assertions ===")
            print("kind=rpc rows remaining:", rpc_rows or "NONE")
            if rpc_rows:
                fails.append("kind=rpc still present")
            if rows2["metasploit"]["status"] != "available":
                fails.append("metasploit not available against double")
            if rows2["burp"]["status"] != "available":
                fails.append("burp not available against double")
            if rows2["ghidra"]["status"] != "available":
                fails.append("ghidra bridge did not spawn: %s" % rows2["ghidra"]["detail"])
            for name in ("sliver", "ida", "jadx", "caldera", "havoc", "mythic"):
                if rows2[name]["status"] == "available":
                    fails.append(f"{name} must NOT be available")

    print("\nPHASE-1 RESULT:", "PASS" if not fails else f"FAIL {fails}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
