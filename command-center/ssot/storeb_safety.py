"""Pass 7 - is store B's content actually at risk, or is it all on the remote?

ast-patch167 HEAD == remote refs/heads/fix/deny-credential-gaps tip exactly. If every one of
its 8 store-unique commits is an ANCESTOR of that tip, they are all on GitHub and store B holds
zero at-risk committed content.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

SSOT = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/ssot")
B = "C:/Users/Prekzursil/source/ast-patch167"


def git(repo: str, *a: str) -> str:
    p = subprocess.run(
        ["git", "-C", repo, *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (
        p.stdout.strip() if p.returncode == 0 else f"__ERR__:{p.stderr.strip()[:100]}"
    )


def is_ancestor(repo: str, a: str, b: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", repo, "merge-base", "--is-ancestor", a, b],
            capture_output=True,
        ).returncode
        == 0
    )


d1 = json.loads((SSOT / "clone-measurements.json").read_text(encoding="utf-8"))
uniq = d1["checkouts"][B]["unique_commits_sample"]
head = d1["checkouts"][B]["head_sha"]
res = {"head": head, "commits": []}

print(f"store B HEAD = {head}  (== remote fix/deny-credential-gaps tip)")
print(f"{'commit':12} {'anc-of-HEAD':12} {'subject'}")
all_safe = True
for c in uniq:
    anc = is_ancestor(B, c, head)
    all_safe &= anc
    subj = git(B, "log", "-1", "--format=%s", c)[:78]
    res["commits"].append({"sha": c, "ancestor_of_head": anc, "subject": subj})
    print(f"{c[:12]:12} {str(anc):12} {subj}")
print(f"\nALL 8 reachable from the pushed tip: {all_safe}")
res["all_reachable_from_pushed_tip"] = all_safe

# CONTROL for is_ancestor (both states): a commit that is NOT an ancestor must report False.
root = git(B, "rev-list", "--max-parents=0", "HEAD").splitlines()[0]
print("\nCONTROL is_ancestor:")
print(f"  root->HEAD (expect True)  = {is_ancestor(B, root, head)}")
print(f"  HEAD->root (expect False) = {is_ancestor(B, head, root)}")
res["control_ancestor_true"] = is_ancestor(B, root, head)
res["control_ancestor_false"] = is_ancestor(B, head, root)

# the two verify worktrees
print("\nstore B worktrees - dirty state and reachability of their detached heads")
for wt in [
    "C:/Users/Prekzursil/source/_verify_M04_tree",
    "C:/Users/Prekzursil/source/_verify_M13",
]:
    h = git(wt, "rev-parse", "HEAD")
    dirty = [
        x for x in git(wt, "status", "--porcelain", "-uall").splitlines() if x.strip()
    ]
    anc = is_ancestor(B, h, head)
    print(f"  {wt:48} HEAD={h[:12]} dirty={len(dirty):4} anc-of-pushed-tip={anc}")
    for x in dirty[:8]:
        print(f"        {x[:100]}")
    res.setdefault("worktrees", []).append(
        {
            "path": wt,
            "head": h,
            "dirty": len(dirty),
            "ancestor_of_pushed_tip": anc,
            "dirty_sample": dirty[:20],
        }
    )

# store B stashes + non-remote local branches (the REPO-TOPOLOGY pr242/244/245/249 claim)
print("\nstore B local branches and stashes")
for ln in git(
    B, "for-each-ref", "--format=%(refname:short) %(objectname:short)", "refs/heads"
).splitlines():
    name = ln.split()[0]
    ahead = git(B, "rev-list", "--count", f"{name}", "--not", head)
    print(f"  {ln:56} commits-not-under-pushed-tip={ahead}")
res["stashes"] = git(B, "stash", "list").splitlines()
print(f"  stashes: {len(res['stashes'])}")

with open(SSOT / "storeb-safety.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(res, fh, indent=2)
