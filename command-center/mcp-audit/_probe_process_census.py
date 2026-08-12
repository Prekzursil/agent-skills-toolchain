"""Re-measure the MCP process census. Drift check vs docs/mcp-consolidation-plan.md
(measured 2026-07-24: 336 MCP procs / 180 distinct cmdlines / 58 dup / 13.24 GB commit).

Deterministic algorithm, not judgement: group by EXACT normalized command line.
Two processes with byte-identical command lines are the same server launched twice.

DETECTOR CONTROL included: the matcher is run against a known-present sentinel
(the python.exe running THIS script) and a known-absent nonsense token, so a zero
reading cannot be a broken matcher masquerading as a clean box.
"""

import collections
import json
import os
import pathlib
import re
import subprocess

OUT = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate/command-center/mcp-audit")

PS = r"""
Get-CimInstance Win32_Process |
  Select-Object ProcessId,ParentProcessId,Name,CommandLine,PrivatePageCount,ThreadCount,HandleCount |
  ConvertTo-Json -Depth 3 -Compress
"""
raw = subprocess.run(
    ["powershell", "-NoProfile", "-NonInteractive", "-Command", PS],
    capture_output=True,
    text=True,
    timeout=300,
)
procs = json.loads(raw.stdout)
print(f"total processes on box : {len(procs)}")

# ---- the MCP matcher -------------------------------------------------------
MCP_PAT = re.compile(
    r"(mcp|modelcontextprotocol|@upstash/context7|repomix|searxng|"
    r"chrome-devtools|playwright|basic-memory|agent-mail|codex|"
    r"cloud-hub|social-hub|search-hub|scholarly_access|paper.search|"
    r"elevenlabs|excel-mcp|pdf-reader|gh-cli-mcp|qlty)",
    re.I,
)


def cmdline(p):
    return (p.get("CommandLine") or "").strip()


mcp = [p for p in procs if MCP_PAT.search(cmdline(p))]

# ---- DETECTOR CONTROL, both states ----------------------------------------
me = os.getpid()
sentinel_present = any(p.get("ProcessId") == me for p in procs)
nonsense = re.compile(r"zzz_no_such_token_zzz_9f3a")
sentinel_absent = sum(1 for p in procs if nonsense.search(cmdline(p)))
# and: can the MCP matcher see a KNOWN mcp process? use a name we independently
# confirmed Connected via `claude mcp list` (cloud-hub runs hub.py).
known_mcp = sum(1 for p in procs if "cloud-hub" in cmdline(p).lower())
print()
print("=== DETECTOR CONTROL (both states) ===")
print(f"  own pid {me} visible in table      : {sentinel_present}   (must be True)")
print(f"  nonsense token matches             : {sentinel_absent}    (must be 0)")
print(
    f"  known-present 'cloud-hub' matches  : {known_mcp}    (must be >0 or the matcher is blind)"
)
print(
    f"  cmdline readable for               : {sum(1 for p in procs if cmdline(p))}/{len(procs)} procs"
)
if not sentinel_present or sentinel_absent or known_mcp == 0:
    print("  !! CONTROL FAILED -- the numbers below are NOT trustworthy")
else:
    print("  control PASSED and it can distinguish present from absent")

# ---- the census ------------------------------------------------------------
by_cmd = collections.Counter(cmdline(p) for p in mcp)
dupes = {c: n for c, n in by_cmd.items() if n > 1}
redundant = sum(n - 1 for n in dupes.values())
commit = sum((p.get("PrivatePageCount") or 0) for p in mcp)
threads = sum((p.get("ThreadCount") or 0) for p in mcp)
handles = sum((p.get("HandleCount") or 0) for p in mcp)

# agent sessions
sessions = collections.Counter(
    p.get("Name")
    for p in procs
    if (p.get("Name") or "").lower() in ("claude.exe", "codex.exe", "grok.exe")
)

print()
print("=== CENSUS (today) vs docs/mcp-consolidation-plan.md (2026-07-24) ===")
rows = [
    ("agent sessions (claude/codex/grok)", sum(sessions.values()), "13"),
    ("MCP-matching processes", len(mcp), "336"),
    ("distinct command lines", len(by_cmd), "180"),
    ("command lines with n>1", len(dupes), "58"),
    ("redundant processes (sum n-1)", redundant, "156"),
    ("commit of MCP procs (GB)", round(commit / 1024**3, 2), "13.24"),
    ("threads / handles", f"{threads} / {handles}", "757 / 22404 (redundant only)"),
]
for label, now, then in rows:
    print(f"  {label:38} now={str(now):>12}   2026-07-24={then}")
print(f"  session breakdown: {dict(sessions)}")

# gross duplication projection, same formula the plan used
proj = 0
for c, n in dupes.items():
    tot = sum((p.get("PrivatePageCount") or 0) for p in mcp if cmdline(p) == c)
    proj += tot * (n - 1) / n
print(
    f"  GROSS dedup projection (GB)            {round(proj / 1024**3, 2)}   2026-07-24=5.92  [PROJECTION not measured saving]"
)

print()
print("=== TOP 15 DUPLICATED COMMAND LINES ===")
for c, n in sorted(dupes.items(), key=lambda kv: -kv[1])[:15]:
    tot = sum((p.get("PrivatePageCount") or 0) for p in mcp if cmdline(p) == c)
    print(f"  n={n:3}  {round(tot / 1024**2):6} MB  {c[:120]}")

# npx-cli.js specifically -- the "76 copies" claim in the lane brief
npx = [p for p in procs if "npx-cli.js" in cmdline(p)]
npx_commit = sum((p.get("PrivatePageCount") or 0) for p in npx)
print()
print("=== npx-cli.js (lane brief claimed 76 copies / ~5.5 GB MCP RAM) ===")
print(f"  npx-cli.js processes now : {len(npx)}")
print(f"  their commit             : {round(npx_commit / 1024**3, 2)} GB")

json.dump(
    {
        "total_processes": len(procs),
        "mcp_processes": len(mcp),
        "distinct_cmdlines": len(by_cmd),
        "duplicated_cmdlines": len(dupes),
        "redundant_processes": redundant,
        "commit_bytes": commit,
        "commit_gb": round(commit / 1024**3, 2),
        "gross_dedup_projection_gb": round(proj / 1024**3, 2),
        "npx_cli_processes": len(npx),
        "npx_cli_commit_gb": round(npx_commit / 1024**3, 2),
        "agent_sessions": dict(sessions),
        "control": {
            "own_pid_visible": sentinel_present,
            "nonsense_matches": sentinel_absent,
            "known_mcp_matches": known_mcp,
            "passed": bool(sentinel_present and not sentinel_absent and known_mcp),
        },
        "top_duplicates": [
            {"n": n, "cmdline": c[:300]}
            for c, n in sorted(dupes.items(), key=lambda kv: -kv[1])[:25]
        ],
    },
    (OUT / "process-census.json").open("w", encoding="utf-8"),
    indent=2,
)
print()
print("wrote process-census.json")
