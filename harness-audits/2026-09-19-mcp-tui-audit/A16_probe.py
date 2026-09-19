import json, os, re, subprocess, tomllib

H = os.path.expanduser("~")
MY = re.compile(r'pdf[-_]?reader|^playwright|postgres|^pubmed', re.I)

def load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"__error__": str(e)}

def show_srv(label, name, srv, extra=()):
    if srv is None:
        print(f"{label}::{name} = ABSENT")
        return
    t = {k: srv.get(k) for k in ("type", "command", "args", "url")}
    env = srv.get("env", {})
    t["env_keys"] = list(env.keys()) if isinstance(env, dict) else str(env)[:60]
    for k in extra:
        v = srv.get(k)
        if isinstance(v, str) and len(v) > 110:
            v = v[:110] + "..."
        t[k] = v
    print(f"{label}::{name} = {json.dumps(t, ensure_ascii=False)}")

print("=== A. registry ~/.agents/agents.json (fresh parse) ===")
reg = load(H + "/.agents/agents.json")
servers = reg.get("mcp", {}).get("servers", {})
print("total_servers:", len(servers), "| syncMode:", reg.get("mcp", {}).get("syncMode", reg.get("syncMode")))
for n in sorted(servers):
    if MY.search(n):
        show_srv("REG", n, servers[n], extra=("targets", "enabled", "note"))
print("REG control (basic-memory present):", "basic-memory" in servers)

print("=== B. ~/.claude.json ===")
cj = load(H + "/.claude.json")
root = cj.get("mcpServers", {})
print("root_mcpServers_count:", len(root))
for n in sorted(root):
    if MY.search(n) or n == "McpHub":
        show_srv("CLAUDE-ROOT", n, root[n])
print("CLAUDE control (github in root):", "github" in root)
projs = cj.get("projects", {})
print("projects_scanned:", len(projs))
hits = 0
for p, pd in projs.items():
    if not isinstance(pd, dict):
        continue
    for field in ("mcpServers", "disabledMcpServers", "enabledMcpServers"):
        d = pd.get(field)
        if isinstance(d, dict):
            keys = [k for k in d if MY.search(k)]
        elif isinstance(d, list):
            keys = [k for k in d if isinstance(k, str) and MY.search(k)]
        else:
            keys = []
        if keys:
            hits += 1
            print(f"CLAUDE-PROJ {p} {field}: {keys[:8]}")
            if field == "mcpServers":
                for k in keys[:8]:
                    show_srv("  srv", k, d[k])
print("CLAUDE-PROJ matches:", hits)

print("=== C. claude settings mcp fields ===")
for p in (H + "/.claude/settings.json", H + "/.claude/settings.local.json"):
    if os.path.exists(p):
        s = load(p)
        for field in ("enabledMcpServers", "disabledMcpServers", "enableAllProjectMcpServers"):
            if field in s:
                print(os.path.basename(p), field, "=", json.dumps(s[field])[:300])
    else:
        print(p, "ABSENT")

print("=== D. .mcp.json files ===")
for p in (H + "/.mcp.json",
          "C:/Users/Prekzursil/source/agent-skills-toolchain/.mcp.json",
          H + "/.claude/.mcp.json"):
    if os.path.exists(p):
        m = load(p).get("mcpServers", {})
        print(p, "count:", len(m))
        for n in sorted(m):
            if MY.search(n) or n == "McpHub":
                show_srv("MCPJSON", n, m[n])
    else:
        print(p, "ABSENT")

print("=== E. codex config.toml ===")
try:
    with open(H + "/.codex/config.toml", "rb") as f:
        tx = tomllib.load(f)
    ms = tx.get("mcp_servers", {})
    print("codex mcp_servers count:", len(ms))
    for n in sorted(ms):
        if MY.search(n):
            show_srv("CODEX", n, ms[n])
    print("CODEX control (basic-memory present):", "basic-memory" in ms)
except Exception as e:
    print("CODEX parse error:", str(e)[:120])

print("=== F. cursor mcp.json ===")
cu = load(H + "/.cursor/mcp.json").get("mcpServers", {})
print("cursor count:", len(cu))
for n in sorted(cu):
    if MY.search(n):
        show_srv("CURSOR", n, cu[n])
print("CURSOR control (basic-memory present):", "basic-memory" in cu)

print("=== G. gemini settings.json ===")
ge = load(H + "/.gemini/settings.json")
gm = ge.get("mcpServers", {})
print("gemini count:", len(gm))
for n in sorted(gm):
    if MY.search(n):
        show_srv("GEMINI", n, gm[n])
print("GEMINI control (context7 present):", "context7" in gm)

print("=== H. McpHub sub-server config ===")
hub_paths = []
for src in (root.get("McpHub", {}),):
    a = src.get("args", []) if isinstance(src, dict) else []
    for x in a:
        if isinstance(x, str) and (".mjs" in x or ".json" in x or ".ts" in x):
            hub_paths.append(x)
hub_paths.append(H + "/.agents/meta-tool/src/hub.mjs")
hub_paths.append(H + "/.agents/meta-tool/hub.json")
seen = set()
for hp in hub_paths:
    if hp in seen or not os.path.exists(hp):
        continue
    seen.add(hp)
    try:
        txt = open(hp, encoding="utf-8", errors="replace").read()
        n = 0
        for line in txt.splitlines():
            if MY.search(line) and n < 10:
                l = line.strip()
                print(f"HUB[{os.path.basename(hp)}] {l[:150]}")
                n += 1
        if n == 0:
            print(f"HUB[{os.path.basename(hp)}] no name matches in {len(txt)} chars")
    except Exception as e:
        print("HUB read error", hp, str(e)[:80])

print("=== I. static package/path checks ===")
npx_cache = os.path.join(H, "AppData", "Local", "npm-cache", "_npx")
pkgs = ["@playwright/mcp", "@sylphx/pdf-reader-mcp", "pubmed-mcp"]
found = {p: [] for p in pkgs}
if os.path.isdir(npx_cache):
    for d in os.scandir(npx_cache):
        nm = os.path.join(d.path, "node_modules")
        for p in pkgs:
            pj = os.path.join(nm, p, "package.json")
            if os.path.exists(pj):
                try:
                    ver = json.load(open(pj, encoding="utf-8")).get("version", "?")
                except Exception:
                    ver = "?"
                found[p].append(f"{d.name[:10]}=>v{ver}")
for p in pkgs:
    print("npx-cache", p, "->", found[p][:4] if found[p] else "NOT-CACHED")
    g = os.path.join(H, "AppData", "Roaming", "npm", "node_modules", p, "package.json")
    print("  global-npm:", os.path.exists(g))
for exe in ("npx", "node", "docker"):
    try:
        w = subprocess.run(["where.exe", exe], capture_output=True, text=True, timeout=15)
        first = (w.stdout.strip().splitlines() or ["NOT-FOUND"])[0]
        print(exe, "->", first)
    except Exception as e:
        print(exe, "-> ERR", str(e)[:60])
try:
    r = subprocess.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                       capture_output=True, text=True, timeout=12)
    if r.returncode == 0:
        lines = [l for l in r.stdout.splitlines() if "postgres" in l.lower() or "pgedge" in l.lower()]
        print("docker images (pgedge/postgres):", lines if lines else "DAEMON-UP, IMAGE-NOT-PULLED")
    else:
        print("docker images rc!=", r.returncode, "|", r.stderr.strip()[:120])
except subprocess.TimeoutExpired:
    print("docker images: TIMEOUT (daemon down/hung)")
except Exception as e:
    print("docker images: ERROR", str(e)[:100])
print("PROBE_DONE")
