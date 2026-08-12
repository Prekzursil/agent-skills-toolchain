"""Verify the inventory's highest-value finding: stranded authored commits.

Read-only. Independent probe: for each scratch checkout, list commits reachable from all refs
AND the reflog, then ask (a) does the CANONICAL store have that object, and (b) is it reachable
from any remote tip. Both-states controls included.
"""
import json
import os
import subprocess

CANON = "C:/Users/Prekzursil/source/agent-skills-toolchain"

SCRATCH = [
    "C:/Users/Prekzursil/.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain",
    "C:/Users/Prekzursil/.claude/agent-worktrees-salvage/agent-425276811/ast",
    "C:/Users/Prekzursil/source/_wu/CRCP-SEC",
    "C:/Users/Prekzursil/work/agent-skills-toolchain-re",
]


def git(repo, *args, timeout=120):
    try:
        p = subprocess.run(
            ["git", "-C", repo] + list(args), capture_output=True, text=True, timeout=timeout
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as exc:  # noqa: BLE001
        return -1, "", repr(exc)


def canon_has(sha):
    rc, _, _ = git(CANON, "cat-file", "-e", f"{sha}^{{commit}}")
    return rc == 0


out = {"controls": {}, "checkouts": []}

# ---- both-states control on the canonical-store detector
rc, canon_head, _ = git(CANON, "rev-parse", "HEAD")
out["controls"]["canonical_head_present"] = canon_has(canon_head)
out["controls"]["fabricated_absent"] = not canon_has("dead" * 10)
out["controls"]["ok"] = (
    out["controls"]["canonical_head_present"] and out["controls"]["fabricated_absent"]
)

# ---- remote tips, fetched once from the canonical store (network)
rc, ls, err = git(CANON, "ls-remote", "--heads", "--tags", "origin", timeout=180)
remote_tips = set()
for line in ls.splitlines():
    parts = line.split()
    if parts:
        remote_tips.add(parts[0])
out["controls"]["remote_tip_count"] = len(remote_tips)
out["controls"]["ls_remote_err"] = err[:200]

for path in SCRATCH:
    row = {"path": path, "exists": os.path.isdir(path)}
    if not row["exists"]:
        out["checkouts"].append(row)
        continue
    rc, common, _ = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    row["git_common_dir"] = common
    row["kind"] = "worktree" if os.path.isfile(os.path.join(path, ".git")) else "clone"
    rc, head, _ = git(path, "rev-parse", "HEAD")
    row["head"] = head
    rc, st, _ = git(path, "status", "--porcelain", "-uall")
    row["dirty_uall"] = len([x for x in st.splitlines() if x.strip()])
    rc, stash, _ = git(path, "stash", "list")
    row["stash"] = len([x for x in stash.splitlines() if x.strip()])

    # commits reachable from refs + reflog (catches orphaned/amended work)
    rc, rl, err = git(path, "rev-list", "--all", "--reflog", "--max-count=4000")
    shas = [x for x in rl.splitlines() if x.strip()]
    row["reachable_commit_count"] = len(shas)
    row["rev_list_err"] = err[:200]

    stranded = []
    for sha in shas:
        if canon_has(sha):
            continue  # canonical already has it -> not unique to this checkout
        if sha in remote_tips:
            continue
        rc, meta, _ = git(path, "show", "-s", "--format=%h|%ad|%an|%s", "--date=short", sha)
        stranded.append({"sha": sha[:12], "meta": meta})
        if len(stranded) >= 40:
            break
    row["stranded_count"] = len(stranded)
    row["stranded"] = stranded
    out["checkouts"].append(row)

out["total_stranded"] = sum(c.get("stranded_count", 0) for c in out["checkouts"])
print(json.dumps(out, indent=2, default=str))
