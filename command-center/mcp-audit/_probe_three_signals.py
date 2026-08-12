"""Cross-tabulate THREE mechanically independent signals about MCP server state.

S1  config resolution   -- mcpctl matrix (reads the 5 on-disk JSON scopes)
S2  host health check   -- `claude mcp list` (the CLI connects to each entry)
S3  session namespace   -- the mcp__<server>__ tool prefixes actually injected into
                           THIS Claude session (transcribed from the deferred-tool list)

S3 is the only one that answers "is this server's capability reachable by the model right
now". S1 answers "what does the config say". S2 answers "can a fresh process connect".
They are NOT the same question, and the whole audit turns on that.
"""

import json
import pathlib
import re

BASE = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/mcp-audit"
)

# ---------------------------------------------------------------- S1
m = json.loads((BASE / "mcpctl-matrix.json").read_text(encoding="utf-8-sig"))
s1 = {r["name"]: r for r in m["rows"]}

# ---------------------------------------------------------------- S2
raw = (BASE / "claude-mcp-list.txt").read_text(encoding="utf-8", errors="replace")
s2 = {}
# "name: <command or url> - <glyph> <Status...>"
pat = re.compile(r"^([A-Za-z0-9_.\- ]+?):\s+(.*?)\s+-\s+(.*)$")
for line in raw.splitlines():
    line = line.strip()
    if not line or line.startswith(("Checking", "\u26a0")):
        continue
    mm = pat.match(line)
    if mm:
        name, cmd, status = mm.group(1), mm.group(2), mm.group(3)
        s2[name] = {"cmd": cmd, "status": status}

# ---------------------------------------------------------------- S3
# Transcribed verbatim from the deferred-tool list injected into this session.
S3_LIVE = sorted(
    {
        "agent-mail",
        "angr",
        "basic-memory",
        "brightdata",
        "chrome-devtools",
        "claude-code-mcp",
        "cloud-hub",
        "codex",
        "context7",
        "deepwiki",
        "figma",
        "frida-mcp",
        "github",
        "huggingface",
        "paper-search",
        "playwright",
        "playwright-cdp",
        "playwright-extension",
        "qlty",
        "repomix",
        "scholarly-access",
        "search-hub",
        "searxng",
    }
)

print("=== SIGNAL SIZES ===")
print(
    f"S1 mcpctl rows          : {len(s1)}  (enabled={sum(1 for r in s1.values() if r['state'] == 'enabled')})"
)
print(f"S2 claude mcp list rows : {len(s2)}")
conn = [n for n, v in s2.items() if "Connected" in v["status"]]
fail = [n for n, v in s2.items() if "Connected" not in v["status"]]
print(f"   connected            : {len(conn)}")
print(f"   not-connected        : {len(fail)}  -> {fail}")
print(f"S3 session namespaces   : {len(S3_LIVE)}")

print()
print("=== THE CROSS-TAB (the point of the whole audit) ===")
allnames = sorted(set(s1) | set(s2) | set(S3_LIVE))
hdr = f"{'server':26} {'S1 config':>16} {'S2 host-check':>16} {'S3 in-session':>14}"
print(hdr)
print("-" * len(hdr))
buckets = {}
for n in allnames:
    a = s1[n]["state"] if n in s1 else "-absent-"
    b = (
        "Connected"
        if n in s2 and "Connected" in s2[n]["status"]
        else ("FAILED" if n in s2 else "-absent-")
    )
    c = "LIVE" if n in S3_LIVE else "-"
    key = (a, b, c)
    buckets.setdefault(key, []).append(n)
    if not (a == "disabled" and b == "-absent-" and c == "-"):
        print(f"{n:26} {a:>16} {b:>16} {c:>14}")

print()
print("=== BUCKET SUMMARY (state-triple -> count) ===")
for k, v in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
    print(f"  {len(v):4}  S1={k[0]:16} S2={k[1]:10} S3={k[2]:5}")

print()
print("=== DISAGREEMENTS THAT MATTER ===")
print("A. S2 says Connected but S3 says the session does NOT have it")
a = sorted(n for n in conn if n not in S3_LIVE)
print(f"   n={len(a)}: {a}")
print()
print("B. S3 LIVE but S1 config says NOT enabled  (config reader would miss these)")
b = sorted(n for n in S3_LIVE if n in s1 and s1[n]["state"] != "enabled")
for n in b:
    print(f"   {n:24} S1={s1[n]['state']:16} basis={s1[n]['basis']}")
print(f"   n={len(b)}")
print()
print("C. S3 LIVE but absent from S1 entirely (config file mcpctl does not read)")
c = sorted(n for n in S3_LIVE if n not in s1)
print(f"   n={len(c)}: {c}")
print()
print("D. S1 enabled but NOT live in session")
d = sorted(n for n, r in s1.items() if r["state"] == "enabled" and n not in S3_LIVE)
print(f"   n={len(d)}: {d}")
print()
print("E. S2 absent entirely but S3 LIVE (host CLI never saw it)")
e = sorted(n for n in S3_LIVE if n not in s2)
print(f"   n={len(e)}: {e}")
