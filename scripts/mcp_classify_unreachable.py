"""Classify the 47 unreachable MCP servers. Script, not 47 agents.

Rung 1 (does the entrypoint EXIST) is what separates package-gone from
backend-on-demand, and it is a filesystem check - no agent needed.
Reachability is a snapshot; the burden of proof is on DELETION.
"""
import collections
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CFG = r"C:\Users\prekzursil\.claude.json"
RE_HARNESS = os.path.expanduser(r"~\.local\opt\re-harness")

DEAD = ['angr','apktool-mcp','biomcp','cheatengine','claude-code-mcp','codacy','codex','docker',
        'elevenlabs','frida-mcp','ghidra-mcp','github_cli','gitlab','ida-pro-mcp','jadx-mcp',
        'mitmproxy','ocr-suite','open-coscientist-lit-review','openmm-md','paper-search',
        'perplexity','postgres','qdx-rush','rdkit','scholarly-access','serena','sonarqube']
AT_HOME = ['McpHub','agent-mail','biomni','breach-intel','cloud-audit','cursor-bridge','cve-mcp',
           'dbx-ai','firecrawl','github','github-security','hexstrike-ai','huggingface','nuclei',
           'osint','semgrep','web-reader','web-search-prime','zai-lane-a','zread']

# Names the estate documents as started ON DEMAND by the RE harness.
ON_DEMAND = {'ghidra-mcp','ida-pro-mcp','jadx-mcp','apktool-mcp','frida-mcp','angr',
             'hexstrike-ai','cheatengine','binary-ninja-mcp'}

cfg = json.load(open(CFG, encoding="utf-8", errors="replace"))
srv = cfg.get("mcpServers") or {}

# which loopback ports currently have a listener
try:
    net = subprocess.run(["pwsh", "-NoProfile", "-Command",
        "(Get-NetTCPConnection -State Listen).LocalPort | Sort-Object -Unique"],
        capture_output=True, text=True, timeout=120).stdout
    LISTEN = {int(x) for x in re.findall(r"\d+", net)}
except Exception:
    LISTEN = set()

harness_files = []
if os.path.isdir(RE_HARNESS):
    for root, _d, fs in os.walk(RE_HARNESS):
        harness_files += [os.path.join(root, f).lower() for f in fs]


def entry_exists(c):
    """Rung 1: does the thing this entry launches actually exist on disk?"""
    cmd = (c.get("command") or "")
    args = c.get("args") or []
    if not cmd:
        return None
    base = os.path.basename(cmd).lower()
    if base in ("cmd", "cmd.exe", "pwsh", "powershell", "npx", "node", "python", "uv", "uvx", "bun", "deno"):
        for a in args:
            if isinstance(a, str) and (a.endswith((".js", ".py", ".mjs", ".ps1")) or ("\\" in a or "/" in a)):
                if os.path.isabs(a):
                    return os.path.exists(a)
        return None                      # package-manager launch; can't decide from path alone
    if os.path.isabs(cmd):
        return os.path.exists(cmd)
    from shutil import which
    return which(cmd) is not None


rows = []
for name in DEAD + AT_HOME:
    c = srv.get(name)
    if not isinstance(c, dict):
        rows.append((name, "not-in-config", "", "DELETE", "absent from mcpServers"))
        continue
    url = c.get("url") or ""
    port = None
    m = re.search(r":(\d{2,5})", url)
    if m:
        port = int(m.group(1))
    has_launcher = any(name.split("-")[0].lower() in f for f in harness_files)
    ex = entry_exists(c)

    if name in ON_DEMAND or has_launcher:
        label, action = "backend-on-demand", "KEEP"
        ev = f"RE-harness launcher present={has_launcher}; documented on-demand={name in ON_DEMAND}"
    elif url:
        up = (port in LISTEN) if port else False
        label = "backend-on-demand" if not up else "unknown"
        action = "KEEP" if name in AT_HOME else "QUARANTINE"
        ev = f"http/sse {url}  listener_on_{port}={up}"
    elif ex is False:
        label, action = "package-gone", "DELETE"
        ev = "rung1: entrypoint does not exist on disk"
    elif ex is True:
        label, action = "unknown", "QUARANTINE"
        ev = "rung1: entrypoint EXISTS but exposed no tools -> not package-gone"
    else:
        label, action = "unknown", "QUARANTINE"
        ev = "package-manager launch; rung1 indeterminate from path"

    if name in AT_HOME and action == "DELETE":
        action, ev = "QUARANTINE", ev + "; but home runs it -> do not delete"
    rows.append((name, label, "on-demand" if has_launcher else "", action, ev))

w = max(len(r[0]) for r in rows) + 1
print(f"{'SERVER':<{w}} {'LABEL':<19} {'ACTION':<11} EVIDENCE")
print("-" * 112)
for r in sorted(rows, key=lambda x: (x[3], x[1], x[0])):
    print(f"{r[0]:<{w}} {r[1]:<19} {r[3]:<11} {r[4][:60]}")

print("\nACTION COUNTS:", dict(collections.Counter(r[3] for r in rows)))
print("LABEL  COUNTS:", dict(collections.Counter(r[1] for r in rows)))
print(f"\nRE-harness dir present: {os.path.isdir(RE_HARNESS)}  ({len(harness_files)} files)")
print(f"listening loopback ports: {len(LISTEN)}")
