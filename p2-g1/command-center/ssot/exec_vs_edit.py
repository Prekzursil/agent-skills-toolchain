"""Pass 8 - the SSOT question that actually matters:
is the checkout the estate EXECUTES from the same one it EDITS in?

Five MCP servers resolve their command/args into ~/source/agent-skills-toolchain (the
main checkout, permanently detached). main lives in ast-integrate. If the detached checkout
is behind main, the fleet is running stale code.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

CANON = "C:/Users/Prekzursil/source/agent-skills-toolchain"
SSOT = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/ssot")


def git(*a: str, repo: str = CANON) -> str:
    p = subprocess.run(
        ["git", "-C", repo, *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (
        p.stdout.strip() if p.returncode == 0 else f"__ERR__:{p.stderr.strip()[:120]}"
    )


head = git("rev-parse", "HEAD")
remote_main = git("ls-remote", "origin", "refs/heads/main").split()[0]
integrate_head = git(
    "rev-parse", "HEAD", repo="C:/Users/Prekzursil/source/ast-integrate"
)

print(f"main checkout (EXECUTED)   {CANON}")
print(
    f"   HEAD                    {head}   {git('log', '-1', '--format=%ad %s', '--date=short', head)[:70]}"
)
print(f"ast-integrate (EDITED)     HEAD {integrate_head}")
print(f"true remote main                {remote_main}")
print()
behind = git("rev-list", "--count", f"{head}..{remote_main}")
ahead = git("rev-list", "--count", f"{remote_main}..{head}")
print(f"executed checkout is BEHIND remote main by : {behind} commits")
print(f"executed checkout is AHEAD  of remote main by: {ahead} commits")

# Which files that MCP servers load have actually changed between the two?
mcp_paths = []
for cfg in ["C:/Users/Prekzursil/.mcp.json", "C:/Users/Prekzursil/.claude.json"]:
    try:
        data = json.loads(Path(cfg).read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        continue
    for name, spec in (data.get("mcpServers") or {}).items():
        blob = json.dumps(spec)
        if "agent-skills-toolchain" in blob:
            tgt = []
            for v in [spec.get("command", "")] + list(spec.get("args") or []):
                if isinstance(v, str) and "agent-skills-toolchain" in v:
                    tgt.append(v)
            mcp_paths.append({"config": Path(cfg).name, "server": name, "targets": tgt})

print("\nMCP servers whose command/args resolve into the EXECUTED checkout:")
seen = set()
rel_dirs = set()
for m in mcp_paths:
    key = (m["server"], tuple(m["targets"]))
    if key in seen:
        continue
    seen.add(key)
    print(f"  [{m['config']:14}] {m['server']:20}")
    for t in m["targets"]:
        tn = t.replace("\\", "/")
        exists = Path(tn).exists()
        print(f"        {tn}   exists_on_disk={exists}")
        i = tn.lower().find("agent-skills-toolchain/")
        if i >= 0:
            rel = tn[i + len("agent-skills-toolchain/") :]
            # map to the repo-relative dir the server loads from
            parts = rel.split("/")
            if parts[0] in ("tools", "scripts", "platform", "ci"):
                rel_dirs.add("/".join(parts[:3]))

print(f"\nrepo-relative dirs the fleet executes from: {sorted(rel_dirs)}")
print("Changes in those dirs between the EXECUTED commit and remote main:")
total = 0
for d in sorted(rel_dirs):
    n = git("diff", "--name-only", f"{head}..{remote_main}", "--", d)
    cnt = len([x for x in n.splitlines() if x.strip()])
    total += cnt
    print(f"  {d:44} changed_files={cnt}")
    for f in [x for x in n.splitlines() if x.strip()][:6]:
        print(f"        {f}")
print(f"  TOTAL changed files under executed dirs: {total}")

out = {
    "executed_head": head,
    "remote_main": remote_main,
    "integrate_head": integrate_head,
    "behind": behind,
    "ahead": ahead,
    "mcp_paths": mcp_paths,
    "executed_dirs": sorted(rel_dirs),
    "changed_files_under_executed_dirs": total,
}
with open(SSOT / "exec-vs-edit.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, indent=2)
