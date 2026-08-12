"""Pass 3 - answer the specific residual questions raised by passes 1-2."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

SSOT = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/ssot")
CANON = "C:/Users/Prekzursil/source/agent-skills-toolchain"


def git(repo: str, *a: str) -> str:
    p = subprocess.run(
        ["git", "-C", repo, *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (
        p.stdout.rstrip("\n")
        if p.returncode == 0
        else f"__ERR__:{p.stderr.strip()[:120]}"
    )


d1 = json.loads((SSOT / "clone-measurements.json").read_text(encoding="utf-8"))
d2 = json.loads((SSOT / "unique-depth.json").read_text(encoding="utf-8"))

print("=" * 78)
print("A. origin URL per checkout  (are they even the same upstream?)")
for p, r in d1["checkouts"].items():
    if r.get("exists"):
        print(f"  {p:52} {r.get('origin_url', '')}")

print()
print("=" * 78)
print("B. decomposition of the 174 canonical commits not on any remote tip")
buckets = Counter()
for ref, v in d2["canonical_local_refs_vs_remote"].items():
    n = v["commits_not_on_remote"]
    if n <= 0:
        continue
    if ref.startswith("refs/claude-checkpoints/"):
        buckets["claude-checkpoints (auto session snapshots)"] += n
    elif ref.startswith("refs/tags/rescue/") or ref.startswith("refs/tags/parked-"):
        buckets["rescue/parked tags (mirrors of branches)"] += n
    elif ref.startswith("refs/heads/"):
        buckets["refs/heads (real unpushed branch work)"] += n
    elif ref == "refs/stash":
        buckets["stash"] += n
    else:
        buckets[ref] += n
for k, v in buckets.most_common():
    print(f"  {k:52} {v}")
print("  NOTE: buckets double-count commits shared by a branch and its rescue tag.")

# exact, de-duplicated: which commits are unpushed and reachable ONLY from heads/stash
tips = [
    s
    for s in set(d2["remote_refs"].values())
    if git(CANON, "cat-file", "-t", s) == "commit"
]
heads = [r for r in d2["canonical_local_refs_vs_remote"] if r.startswith("refs/heads/")]
uniq_heads = subprocess.run(
    ["git", "-C", CANON, "rev-list", *heads, "--not", *tips],
    capture_output=True,
    text=True,
    encoding="utf-8",
).stdout.split()
print(
    f"  DEDUPED: commits on refs/heads/* not reachable from any remote tip = {len(uniq_heads)}"
)
for c in uniq_heads:
    print(
        "    ", git(CANON, "log", "-1", "--format=%h %ad %s", "--date=short", c)[:110]
    )

print()
print("=" * 78)
print("C. ast-patch167 - is its work already on the remote?")
p167 = "C:/Users/Prekzursil/source/ast-patch167"
head = d1["checkouts"][p167]["head_sha"]
rb = d2["remote_refs"].get("refs/heads/fix/deny-credential-gaps", "ABSENT")
print(f"  local HEAD                 {head}")
print(f"  remote fix/deny-cred...    {rb}")
print(f"  IDENTICAL                  {head == rb}")
print(
    f"  remote tip present locally? {git(p167, 'cat-file', '-t', rb) if rb != 'ABSENT' else 'n/a'}"
)
print(
    f"  merge-base with remote main present in clone: "
    f"{d2['clone_unique_detail'].get(p167, {}).get('merge_base_with_remote_main_present')}"
)

print()
print("=" * 78)
print("D. work/agent-skills-toolchain-re - shared history with canonical?")
pre = "C:/Users/Prekzursil/work/agent-skills-toolchain-re"
print(f"  HEAD              {d1['checkouts'][pre]['head_sha']}")
print(f"  remote main       {d1['remote_main_sha']}")
print(
    f"  HEAD==remote main {d1['checkouts'][pre]['head_sha'] == d1['remote_main_sha']}"
)
print("  refs in clone:")
for r in d1["checkouts"][pre]["refs"]:
    print("    ", r)
print(
    f"  reachable commits {d1['checkouts'][pre]['reachable_commit_count']} "
    f"(canonical has {d1['checkouts'][CANON]['reachable_commit_count']})"
)
# are the 7 unique commits ancestors of main, or an orphan line?
for c in d1["checkouts"][pre]["unique_commits_sample"]:
    anc = subprocess.run(
        ["git", "-C", pre, "merge-base", "--is-ancestor", c, "HEAD"],
        capture_output=True,
    ).returncode
    print(f"    {c[:12]} ancestor-of-HEAD={anc == 0}")

print()
print("=" * 78)
print("E. uncommitted work per checkout (is it real, or ignorable churn?)")
for p, v in d2["dirty_detail"].items():
    print(f"\n  {p}   tracked={v['tracked']} untracked={v['untracked']}")
    for s in v["sample"][:18]:
        print(f"      {s[:112]}")
    if v["count"] > 18:
        print(f"      ... {v['count'] - 18} more")

print()
print("=" * 78)
print("F. junction / reparse-point hazards (git worktree remove follows these)")
for p, r in d1["checkouts"].items():
    if r.get("exists") and (r.get("junctions_at_root") or r.get("root_is_reparse")):
        print(
            f"  {p}  root_is_reparse={r['root_is_reparse']}  {r['junctions_at_root']}"
        )
print("  (empty above = none found at checkout roots)")
