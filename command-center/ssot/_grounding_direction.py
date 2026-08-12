"""Two-directional line diff + deliberate-deletion control.

Two questions the one-directional read cannot answer:
 (Q-A) Is `tools/mcp-manager/` ABSENT from main because the work is stranded, or because the tree
       was DELIBERATELY retired (the agentify-desktop trap in REPO-TOPOLOGY.md)?
 (Q-B) For the DIVERGED mcpctl/crcp files, does main hold the FIX, or only the scratch tree?
       Measured BOTH directions: lines only-in-scratch AND lines only-in-main.
Read-only.
"""
import json
import subprocess

CANON = "C:/Users/Prekzursil/source/agent-skills-toolchain"
INTEG = "C:/Users/Prekzursil/source/ast-integrate"
B5 = "C:/Users/Prekzursil/.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain"
MCPCTL = "C:/Users/Prekzursil/.claude/agent-worktrees-salvage/agent-425276811/ast"


def git(repo, *args, timeout=120):
    p = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def blob(repo, rev, path):
    rc, o = git(repo, "cat-file", "-p", f"{rev}:{path}")
    return o if rc == 0 else None


def lines(text):
    if text is None:
        return set()
    return {ln.rstrip("\r") for ln in text.splitlines() if ln.strip()}


out = {}

# ---------------- Q-A: does tools/mcp-manager exist on main at all?
rc, tree = git(INTEG, "ls-tree", "-r", "--name-only", "origin/main", "tools/mcp-manager/")
main_files = [x for x in tree.splitlines() if x.strip()]
rc, tree_b5 = git(B5, "ls-tree", "-r", "--name-only", "80130e1f", "tools/mcp-manager/")
b5_files = [x for x in tree_b5.splitlines() if x.strip()]
# CONTROL: the same ls-tree over a directory that certainly exists on main
rc, ctl = git(INTEG, "ls-tree", "-r", "--name-only", "origin/main", "tools/mcpctl/")
ctl_files = [x for x in ctl.splitlines() if x.strip()]
out["QA_mcp_manager"] = {
    "files_on_main": len(main_files),
    "files_in_b5_commit": len(b5_files),
    "control_mcpctl_files_on_main": len(ctl_files),
    "control_fires": len(ctl_files) > 0,
    "main_sample": main_files[:12],
    "b5_sample": b5_files[:12],
}
# was it ever there, then deleted? search main history for the path
rc, hist = git(
    INTEG, "log", "--oneline", "-15", "--diff-filter=D", "origin/main", "--",
    "tools/mcp-manager/",
)
out["QA_mcp_manager"]["main_deletion_commits"] = [
    x for x in hist.splitlines() if x.strip()
]
rc, anyhist = git(INTEG, "log", "--oneline", "-10", "origin/main", "--", "tools/mcp-manager/")
out["QA_mcp_manager"]["main_history_touching_path"] = [
    x for x in anyhist.splitlines() if x.strip()
]

# ---------------- Q-B: two-directional line diff
pairs = [
    (MCPCTL, "4a4f7c97", "tools/mcpctl/mcpctl/safety.py"),
    (MCPCTL, "4a4f7c97", "tools/mcpctl/tests/test_safety.py"),
    ("C:/Users/Prekzursil/source/_wu/CRCP-SEC", "c7ffc20f", "tools/crcp/crcp/auth_broker.py"),
    ("C:/Users/Prekzursil/source/_wu/CRCP-SEC", "c7ffc20f", "tools/crcp/crcp/__main__.py"),
]
qb = []
for repo, sha, path in pairs:
    s = blob(repo, sha, path)
    m = blob(INTEG, "origin/main", path)
    sl, ml = lines(s), lines(m)
    only_scratch = sorted(sl - ml)
    only_main = sorted(ml - sl)
    row = {
        "path": path,
        "only_in_scratch": len(only_scratch),
        "only_in_main": len(only_main),
        "scratch_sample": only_scratch[:8],
        "main_sample": only_main[:5],
    }
    if not only_scratch and not only_main:
        row["direction"] = "IDENTICAL"
    elif not only_scratch:
        row["direction"] = "MAIN_IS_SUPERSET (scratch adds nothing)"
    elif not only_main:
        row["direction"] = "SCRATCH_IS_SUPERSET (main is missing scratch lines)"
    else:
        row["direction"] = "DIVERGED_BOTH_WAYS"
    qb.append(row)
out["QB_two_directional"] = qb

print(json.dumps(out, indent=2, default=str))
