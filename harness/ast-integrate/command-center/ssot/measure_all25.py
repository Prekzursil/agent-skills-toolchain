"""Pass 9 - re-measure the FULL 25-checkout fleet the exhaustive sweep found.

Two corrections forced by the sweep:
  1. 25 checkouts / 18 stores, not the 14 / 8 I had from the hand-written lists.
  2. `git status --porcelain` WITHOUT -uall collapses untracked directories and under-counts.
     REPO-TOPOLOGY.md detector-note 3 says exactly this; I read it and failed to apply it.
     Every dirty count here is -uall.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

SSOT = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/ssot")
sweep = json.loads((SSOT / "full-sweep.json").read_text(encoding="utf-8"))
PATHS = [m["path"] for m in sweep["matches"]]


def git(repo: str, *a: str) -> str:
    p = subprocess.run(
        ["git", "-C", repo, *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout.rstrip("\n") if p.returncode == 0 else ""


def lines(repo: str, *a: str) -> list[str]:
    return [x for x in git(repo, *a).splitlines() if x.strip()]


def batch_present(repo: str, shas: list[str]) -> set[str]:
    if not shas:
        return set()
    p = subprocess.run(
        ["git", "-C", repo, "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        input="\n".join(shas) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        ln.split()[0]
        for ln in p.stdout.splitlines()
        if len(ln.split()) == 2 and ln.split()[1] == "commit"
    }


# store identity per path
store_of = {
    m["path"]: m["git_common_dir"].lower().rstrip("/") for m in sweep["matches"]
}
one_repo_per_store: dict[str, str] = {}
for p, s in store_of.items():
    one_repo_per_store.setdefault(s, p)

remote_main = (
    git(PATHS[0], "ls-remote", "origin", "refs/heads/main").split()[0] if PATHS else ""
)

rows = []
reach_cache: dict[str, set[str]] = {}
for p in PATHS:
    reach_cache[store_of[p]] = reach_cache.get(store_of[p]) or set(
        lines(p, "rev-list", "--all", "--reflog")
    )

for p in PATHS:
    s = store_of[p]
    dirty = lines(p, "status", "--porcelain", "-uall")
    row = {
        "path": p,
        "store": s,
        "branch": git(p, "rev-parse", "--abbrev-ref", "HEAD"),
        "head": git(p, "rev-parse", "HEAD"),
        "dirty_uall": len(dirty),
        "dirty_tracked": len([x for x in dirty if not x.startswith("??")]),
        "stashes": len(lines(p, "stash", "list")),
        "origin": git(p, "config", "--get", "remote.origin.url"),
    }
    rows.append(row)

# unique commits per STORE (not per checkout - worktrees share)
store_unique = {}
for s, rep in one_repo_per_store.items():
    mine = reach_cache[s]
    elsewhere: set[str] = set()
    for s2, rep2 in one_repo_per_store.items():
        if s2 == s:
            continue
        elsewhere |= batch_present(rep2, sorted(mine))
    uniq = sorted(mine - elsewhere)
    # of those, which are NOT reachable from any remote tip this store holds?
    remote_tips = [ln.split()[0] for ln in lines(rep, "ls-remote", "origin")]
    tips_local = sorted(batch_present(rep, sorted(set(remote_tips))))
    not_pushed = (
        set(lines(rep, "rev-list", "--all", "--reflog", "--not", *tips_local))
        if tips_local
        else set(mine)
    )
    store_unique[s] = {
        "representative": rep,
        "reachable": len(mine),
        "unique_to_this_store": len(uniq),
        "unique_and_not_on_remote": len(sorted(set(uniq) & not_pushed)),
        "sample": [
            f"{c[:10]} {git(rep, 'log', '-1', '--format=%ad %s', '--date=short', c)[:74]}"
            for c in sorted(set(uniq) & not_pushed)[:6]
        ],
    }

print(f"{'checkout':62} {'branch':44} {'dirty':>6} {'stash':>5}")
for r in sorted(rows, key=lambda x: x["path"]):
    print(
        f"{r['path']:62} {r['branch'][:43]:44} {r['dirty_uall']:>6} {r['stashes']:>5}"
    )

print(f"\n{'STORE':78} {'reach':>6} {'uniq':>5} {'uniq&unpushed':>14}")
for s, v in sorted(
    store_unique.items(), key=lambda kv: -kv[1]["unique_and_not_on_remote"]
):
    print(
        f"{s[:78]:78} {v['reachable']:>6} {v['unique_to_this_store']:>5} {v['unique_and_not_on_remote']:>14}"
    )
    for line in v["sample"]:
        print(f"      {line}")

out = {"remote_main": remote_main, "rows": rows, "store_unique": store_unique}
with open(SSOT / "all25.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, indent=2)
print(f"\nwrote {SSOT / 'all25.json'}")
print(
    f"TOTAL checkouts={len(rows)} stores={len(store_unique)} "
    f"dirty_total={sum(r['dirty_uall'] for r in rows)}"
)
