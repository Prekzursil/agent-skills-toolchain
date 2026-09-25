"""Triage the VM's 88 registered MCP servers: registered vs REACHABLE vs present-at-home.

"Connected" is derived from this session's actual tool surface (the mcp__<server>__* prefixes
the harness exposed), which is the authoritative oracle for reachability - not the config file,
which lists intent. claude_ai_* and plugin_* are excluded: they are remote connectors and
plugin-provided servers, not entries in mcpServers.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VM = r"C:\Users\prekzursil\.claude.json"
HOME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "home", ".claude.json")

# Servers that exposed tools in THIS session => the process started and spoke MCP.
CONNECTED = {
    "annas-archive", "arxiv", "basic-memory", "binary-ninja-mcp", "brightdata", "browserstack",
    "chrome-devtools", "claude-in-chrome", "cloud-hub", "codecov", "context7", "crossref",
    "deepscan", "deepsource", "digitalocean", "excel", "figma", "figma-rest", "linear",
    "linkedin", "mcp-graphql", "mcp-windbg", "notion", "openalex", "pdf-reader", "playwright",
    "playwright-cdp", "playwright-extension", "pubmed", "qlty", "ralph-orchestrator", "repomix",
    "sci-hub", "scrapegraph", "search-hub", "searxng", "sentry", "social-hub", "tavily",
    "tooluniverse", "video-agent-kit", "zai-mcp-server",
}


def parse_npx(cfg):
    cmd = (cfg.get("command") or "").lower()
    args = list(cfg.get("args") or [])
    if cmd in ("cmd", "cmd.exe"):
        while args and args[0].lower() in ("/c", "/k"):
            args.pop(0)
        if not args:
            return None
        cmd = args.pop(0).lower()
    return "npx" in cmd


vm = json.load(open(VM, encoding="utf-8", errors="replace")).get("mcpServers") or {}
home = set(json.load(open(HOME, encoding="utf-8", errors="replace")).get("mcpServers") or {})

rows = []
for name, c in sorted(vm.items()):
    if not isinstance(c, dict):
        continue
    if c.get("url") or c.get("type") in ("http", "sse"):
        transport = "http"
    elif parse_npx(c):
        transport = "npx"
    else:
        transport = "direct"
    rows.append({"name": name, "transport": transport,
                 "reachable": name in CONNECTED, "at_home": name in home})

n = len(rows)
reach = sum(r["reachable"] for r in rows)
print(f"VM registered MCP servers : {n}")
print(f"  reachable this session  : {reach}")
print(f"  NOT reachable           : {n - reach}   <- registered surface that returns nothing")
print(f"  present at HOME         : {sum(r['at_home'] for r in rows)}")

print("\n=== DEAD ENTRIES: registered but unreachable, and HOME does not run them either ===")
print("    (the user's explicit deletion priority: 'orphan MCP server entries')")
dead = [r for r in rows if not r["reachable"] and not r["at_home"]]
for r in dead:
    print(f"  {r['transport']:<7} {r['name']}")
print(f"  -> {len(dead)} deletion candidates")

print("\n=== unreachable BUT present at home (do NOT delete - home keeps them) ===")
keep = [r for r in rows if not r["reachable"] and r["at_home"]]
for r in keep:
    print(f"  {r['transport']:<7} {r['name']}")
print(f"  -> {len(keep)}")

print("\n=== the 23 npx entries, by verdict ===")
DEPS = {"annas-archive": 119, "binary-ninja-mcp": 108, "browserstack": 376, "chrome-devtools": 1,
        "claude-code-mcp": 95, "codacy": 1392, "codecov": 95, "digitalocean": 1, "figma-rest": 135,
        "gitlab": 146, "mcp-graphql": 107, "openalex": 43, "pdf-reader": 2, "playwright": 3,
        "playwright-cdp": 3, "playwright-extension": 3, "pubmed": 126, "repomix": 171,
        "sci-hub": 0, "searxng": 108, "sentry": 113, "tavily": 125, "zai-mcp-server": 95}
tierA, tierB, tierC = [], [], []
for r in rows:
    if r["transport"] != "npx":
        continue
    d = DEPS.get(r["name"], -1)
    if not r["reachable"] or r["name"] == "sci-hub":
        tierA.append((r["name"], d))
    elif d <= 5:
        tierB.append((r["name"], d))
    else:
        tierC.append((r["name"], d))
for label, tier, note in (("A DELETE  ", tierA, "unreachable or quarantined - do not migrate"),
                          ("B MIGRATE ", tierB, "cheap + working"),
                          ("C HOLD    ", tierC, "working but heavy dependency tree")):
    print(f"\n  TIER {label} ({len(tier)})  {note}")
    for nm, d in sorted(tier, key=lambda x: -x[1]):
        print(f"      {nm:<24} deps={d}")
print(f"\n  tier C total deps = {sum(d for _, d in tierC)}")
