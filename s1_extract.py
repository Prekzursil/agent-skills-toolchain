# S1 lane: extract cloud-hub / search-hub / tooluniverse configs from registry + live surface
import json, os

targets = ["cloud-hub", "search-hub", "tooluniverse"]

reg_path = r"C:\Users\Prekzursil\.agents\agents.json"
live_path = r"C:\Users\Prekzursil\.claude.json"

out = {}

with open(reg_path, "r", encoding="utf-8") as f:
    reg = json.load(f)
servers = reg.get("mcp", {}).get("servers", {})
print("registry total servers:", len(servers))
for name in targets:
    e = servers.get(name)
    if e is None:
        # try fuzzy: find keys containing the name
        near = [k for k in servers if name.split("-")[0] in k.lower() or name.replace("-", "_") in k.lower().replace("-", "_")]
        print(f"[{name}] NOT in registry; near keys: {near[:8]}")
    else:
        out[name] = {"src": "registry", **e}

with open(live_path, "r", encoding="utf-8") as f:
    live = json.load(f)
lm = live.get("mcpServers", {})
print("live claude mcpServers total:", len(lm))
for name in targets:
    e = lm.get(name)
    if e is None:
        print(f"[{name}] NOT in live claude mcpServers")
    else:
        out.setdefault(name, {})["claude_live"] = e

# Also check top-level projects' disabledMcpServers for these names (scope context only)
print(json.dumps(out, indent=1, default=str)[:4500])
