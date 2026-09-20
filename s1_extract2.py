import json

targets = ["search-hub", "tooluniverse"]

def compact(e):
    if e is None:
        return None
    c = {"command": e.get("command"), "args": e.get("args"), "type": e.get("type"), "transport": e.get("transport"), "url": e.get("url")}
    env = e.get("env")
    if env:
        c["env_keys"] = sorted(env.keys())
        c["env_sample"] = {k: v for k, v in list(env.items())[:3]}
    for extra in ("requiredEnv", "enabled", "description"):
        if extra in e:
            c[extra] = e[extra]
    return c

with open(r"C:\Users\Prekzursil\.agents\agents.json", "r", encoding="utf-8") as f:
    reg = json.load(f)
servers = reg.get("mcp", {}).get("servers", {})

with open(r"C:\Users\Prekzursil\.claude.json", "r", encoding="utf-8") as f:
    live = json.load(f)
lm = live.get("mcpServers", {})

for name in targets:
    print("=== " + name + " ===")
    print("REGISTRY:", json.dumps(compact(servers.get(name)), indent=1))
    print("CLAUDE_LIVE:", json.dumps(compact(lm.get(name)), indent=1))
    # near-miss keys
    near = [k for k in servers if "search" in k.lower() or "tooluniv" in k.lower() or "tool_univ" in k.lower()]
    if near:
        print("near-registry-keys:", near[:10])
