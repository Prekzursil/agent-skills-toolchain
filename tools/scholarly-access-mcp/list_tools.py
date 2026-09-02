"""Print the MCP tool surface (name + one-line doc). Run: python list_tools.py"""

import asyncio

from scholarly_access.server import mcp


async def main():
    tools = await mcp.list_tools()
    print(f"{mcp.name}: {len(tools)} tools")
    width = max(len(t.name) for t in tools)
    for t in tools:
        first = (t.description or "").strip().splitlines()[0]
        print(f"  {t.name:{width}s} {first}")


if __name__ == "__main__":
    asyncio.run(main())
