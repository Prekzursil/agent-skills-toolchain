#!/usr/bin/env python3
"""Final-state verification (rpc-dispatch lane 2026-09-30): gateway freshly
restarted with the corrected SSOT; no test doubles anywhere. Confirms the
steady-state honesty of every converted/reclassified row."""
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
            rows = {b["name"]: b for b in caps["backends"]}
            wanted = ["metasploit", "sliver", "burp", "ghidra", "ida", "jadx",
                      "caldera", "havoc", "mythic"]
            for name in wanted:
                b = rows[name]
                print(f"[{name}] kind={b['kind']} status={b['status']}")
                print(f"    detail: {b['detail'][:230]}")
                if b["kind"] == "rpc":
                    fails.append(f"{name} still kind=rpc")
            avail = sorted(n for n, b in rows.items() if b["status"] == "available")
            unavail = sorted(n for n, b in rows.items() if b["status"] != "available")
            print("\navailable (%d): %s" % (len(avail), avail))
            print("unavailable (%d): %s" % (len(unavail), unavail))
            if rows["ghidra"]["status"] != "available":
                fails.append("ghidra should be available (bridge spawns)")
            for name in ("metasploit", "burp", "sliver", "ida", "jadx", "caldera", "havoc", "mythic"):
                if rows[name]["status"] == "available":
                    fails.append(f"{name} must not be available in steady state")
    print("\nFINAL-STATE RESULT:", "PASS" if not fails else f"FAIL {fails}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
