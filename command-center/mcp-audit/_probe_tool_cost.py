"""Measure per-server TOOL COUNT and DESCRIPTION BYTES from repo-local MCP server source.

Exact where the server is repo-local (we can count its registrations); marked
UNMEASURED otherwise. This is the COST axis: every mounted server spends context on
tool names (always) and tool descriptions (when not deferred).

DETECTOR CONTROL: the counter is run against a file with a KNOWN registration count
before its zero readings are believed.
"""

import json
import pathlib
import re

ROOT = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate")
OUT = ROOT / "command-center/mcp-audit"

# repo-local MCP servers, name -> source glob
LOCAL = {
    "cloud-hub": ["tools/mcp/cloud-hub"],
    "search-hub": ["tools/mcp/search-hub"],
    "social-hub": ["tools/mcp/social-hub"],
    "scholarly-access": ["tools/scholarly-access-mcp"],
    "hexstrike-ai": ["tools/mcp/hexstrike-ai"],
    "qdx-rush": ["tools/mcp/qdx-rush-mcp"],
    "schrodinger": ["tools/mcp/schrodinger-mcp"],
    "codex-fleet-github": ["tools/mcp/codex-fleet-github"],
    "tiktok": ["tools/mcp/tiktok-mcp"],
    "digitalocean": ["tools/mcp/digitalocean-mcp"],
    "openmm-md": ["tools/mcp/openmm-md-mcp"],
    "patent-search": ["tools/mcp/patent-search-mcp"],
    "fb-messenger": ["tools/mcp/fb-messenger-mcp"],
    "linkedin": ["tools/mcp/linkedin-mcp"],
    "hacktricks": ["tools/mcp/hacktricks-mcp-server"],
    "proxy-mcp": ["tools/mcp/proxy-mcp"],
    "omniaudit": ["tools/omniaudit-mcp"],
    "taskwatch": ["tools/taskwatch_monitor/mcp_server"],
}

# Tool-registration shapes across the FastMCP / raw-MCP dialects used on this box.
REG = [
    re.compile(r"@(?:\w+\.)?tool\s*\(", re.M),  # @mcp.tool( / @server.tool(
    re.compile(r"^\s*Tool\s*\(\s*name\s*=", re.M),  # Tool(name=...)
    re.compile(r'"name"\s*:\s*"[a-z0-9_\-]+"\s*,\s*"description"', re.I),
]
# description payloads we can size
DESC = re.compile(
    r'description\s*=\s*(?:f?"""(.*?)"""|f?"([^"]*)"|f?\'([^\']*)\')', re.S
)


def scan(dirpath: pathlib.Path):
    n_tools, desc_bytes, files = 0, 0, 0
    if not dirpath.exists():
        return None
    for f in dirpath.rglob("*.py"):
        if (
            "__pycache__" in str(f)
            or "/tests/" in f.as_posix()
            or "/.venv/" in f.as_posix()
        ):
            continue
        try:
            t = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files += 1
        hits = sum(len(p.findall(t)) for p in REG)
        n_tools += hits
        for m in DESC.finditer(t):
            desc_bytes += len(m.group(1) or m.group(2) or m.group(3) or "")
    return {"tools": n_tools, "desc_bytes": desc_bytes, "py_files": files}


# ---------------- DETECTOR CONTROL --------------------------------------------
ctl_src = "@mcp.tool()\ndef a(): pass\n@mcp.tool()\ndef b(): pass\n"
ctl_hits = sum(len(p.findall(ctl_src)) for p in REG)
ctl_neg = sum(len(p.findall("def plain(): pass\n")) for p in REG)
print("=== DETECTOR CONTROL (both states) ===")
print(f"  known-2-tool fixture -> {ctl_hits}   (must be 2)")
print(f"  known-0-tool fixture -> {ctl_neg}   (must be 0)")
control_ok = ctl_hits == 2 and ctl_neg == 0
print(f"  control {'PASSED' if control_ok else 'FAILED -- counts below untrustworthy'}")
print()

results = {}
print(f"{'server':22} {'tools':>7} {'desc KB':>9} {'py files':>9}  source")
print("-" * 78)
for name, paths in LOCAL.items():
    agg = {"tools": 0, "desc_bytes": 0, "py_files": 0}
    found = False
    for p in paths:
        r = scan(ROOT / p)
        if r:
            found = True
            for k in agg:
                agg[k] += r[k]
    if not found:
        results[name] = "UNMEASURED - source dir absent"
        print(f"{name:22} {'-':>7} {'-':>9} {'-':>9}  ABSENT {paths[0]}")
        continue
    results[name] = agg
    print(
        f"{name:22} {agg['tools']:>7} {agg['desc_bytes'] / 1024:>9.1f} {agg['py_files']:>9}  {paths[0]}"
    )

print()
print("NOTE: third-party servers (playwright, github, figma, context7, deepwiki,")
print("      huggingface, repomix, chrome-devtools, brightdata, angr, agent-mail,")
print("      basic-memory, codex, frida-mcp, searxng, claude-code-mcp, qlty) are")
print("      NOT repo-local; their tool count is UNMEASURED by this probe and must")
print("      come from the session namespace census instead.")

json.dump(
    {"control_passed": control_ok, "servers": results},
    (OUT / "tool-cost-local.json").open("w", encoding="utf-8"),
    indent=2,
)
print("\nwrote tool-cost-local.json")
