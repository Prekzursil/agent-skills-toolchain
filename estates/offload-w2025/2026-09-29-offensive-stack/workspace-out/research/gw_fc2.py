import requests, json
S = requests.Session()
H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
r = S.post("http://127.0.0.1:31100/mcp", json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"research","version":"1.0"}}}, headers=H, timeout=30)
sid = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id")
print("session:", sid)
H2 = dict(H)
if sid: H2["mcp-session-id"] = sid
def rpc(method, params, i):
    rr = S.post("http://127.0.0.1:31100/mcp", json={"jsonrpc":"2.0","id":i,"method":method,"params":params}, headers=H2, timeout=90)
    for line in rr.text.splitlines():
        if line.startswith("data: "):
            try: return json.loads(line[6:])
            except: pass
    return {"raw": rr.text[:400]}
S.post("http://127.0.0.1:31100/mcp", json={"jsonrpc":"2.0","method":"notifications/initialized"}, headers=H2, timeout=30)
t = rpc("tools/list", {}, 2)
names = [x["name"] for x in (t.get("result") or {}).get("tools", [])]
print("tools:", len(names))
print([n for n in names if any(k in n.lower() for k in ("firecrawl","tavily","exa","search"))][:12])
target = next((n for n in names if "firecrawl" in n.lower()), None) or next((n for n in names if "search" in n.lower()), None)
if target:
    args = {"query": "agentic offensive security tools 2026 github", "limit": 5}
    r2 = rpc("tools/call", {"name": target, "arguments": args}, 3)
    txt = json.dumps(r2)
    print(f"\n-- {target} result (first 1200 chars):")
    print(txt[:1200])
