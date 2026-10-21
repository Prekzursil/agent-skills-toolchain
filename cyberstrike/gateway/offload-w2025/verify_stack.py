#!/usr/bin/env python3
"""verify_stack.py - end-to-end verification of the CyberStrike gateway estate.

Connects to the gateway MCP endpoint, lists capabilities, then live-invokes
one tool on each wired backend.
"""
import asyncio
import json
import os
import subprocess
import sys

# The estate stack (gateway-server.py + the `mcp` package) lives on the VM's
# canonical interpreter. `python` on PATH may resolve to another install that
# lacks `mcp` (e.g. C:\Python312) - re-exec under the estate interpreter once
# instead of failing. If `mcp` is missing there too, the import below still
# fails loudly; nothing is skipped or weakened.
ESTATE_PY = r"C:\Python314\python.exe"

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
except ModuleNotFoundError:
    if (os.path.abspath(sys.executable) != os.path.abspath(ESTATE_PY)
            and not os.environ.get("_VERIFY_STACK_REEXEC")):
        env = {**os.environ, "_VERIFY_STACK_REEXEC": "1"}
        sys.exit(subprocess.run(
            [ESTATE_PY, os.path.abspath(__file__), *sys.argv[1:]],
            env=env).returncode)
    raise

GATEWAY = "http://127.0.0.1:31100/mcp"


async def main() -> int:
    failures = []
    async with streamablehttp_client(GATEWAY) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("gateway tools:", [t.name for t in tools.tools])

            caps = await s.call_tool("harness_capabilities", {})
            manifest = json.loads(caps.content[0].text)
            available = {b["name"] for b in manifest["backends"] if b["status"] == "available"}
            print(f"\nAVAILABLE backends ({len(available)}):", sorted(available))
            print("unavailable:", sorted(
                b["name"] for b in manifest["backends"] if b["status"] != "available"))

            probes = [
                ("exa", "search", {"query": "PentAGI autonomous pentest", "limit": 3}),
                ("tavily", "search", {"query": "HexStrike AI MCP tools", "limit": 3}),
                ("firecrawl", "search", {"query": "CyberStrike offensive CLI", "limit": 3}),
                ("nuclei", "-version", {"argv": []}),
                ("nmap", "--version", {"argv": []}),
            ]
            for backend, tool, args in probes:
                if backend not in available:
                    print(f"\n[{backend}] SKIP (unavailable)")
                    continue
                try:
                    res = await s.call_tool("harness_invoke", {
                        "backend": backend, "tool": tool, "arguments": json.dumps(args)})
                    text = res.content[0].text
                    out = json.loads(text)
                    body = out.get("stdout") or out.get("result") or out
                    summary = str(body)[:220].replace("\n", " ")
                    print(f"\n[{backend}.{tool}] OK -> {summary}")
                except Exception as exc:  # noqa: BLE001
                    failures.append(backend)
                    print(f"\n[{backend}.{tool}] FAIL {exc}")
    print("\nFAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
