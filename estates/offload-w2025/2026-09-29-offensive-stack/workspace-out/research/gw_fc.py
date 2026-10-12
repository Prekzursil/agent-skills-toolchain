import requests, json
S = requests.Session()
H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
def rpc(method, params, i):
    r = S.post("http://127.0.0.1:31100/mcp", json={"jsonrpc":"2.0","id":i,"method":method,"params":params}, headers=H, timeout=60)
    for line in r.text.splitlines():
        if line.startswith("data: "):
            try: return json.loads(line[6:])
            except: pass
    try: return r.json()
    except: return {"raw": r.text[:300]}

init = rpc("initialize", {"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"research","version":"1.0"}}, 1)
rpc("notifications/initialized", {}, 2)
tools = rpc("tools/list", {}, 3)
names = []
if "result" in tools:
    for t in tools["result"].get("tools", []):
        names.append(t["name"])
print("GATEWAY TOOLS:", len(names))
fc = [n for n in names if "firecrawl" in n.lower() or "search" in n.lower()]
print("search-ish tools:", fc)
# try a firecrawl-backed search tool
target = next((n for n in names if "firecrawl" in n.lower()), None)
if target:
    r = rpc("tools/call", {"name": target, "arguments": {"query": "new agentic offensive security tools 2026 github", "limit": 5}}, 4)
    print(f"\n--- tools/call {target} ---")
    print(json.dumps(r, indent=1)[:1500])
