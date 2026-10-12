import asyncio, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def call(tool, args):
    async with streamablehttp_client("http://127.0.0.1:31100/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("harness_invoke", {"backend":"darknet","tool":tool,"arguments":json.dumps(args) if not isinstance(args,str) else args})
            return res.content[0].text

if __name__ == "__main__":
    tool = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    out = asyncio.run(call(tool, args))
    print(out[:6000])
