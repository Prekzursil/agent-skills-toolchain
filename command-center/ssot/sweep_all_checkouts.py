"""Pass 6 - EXHAUSTIVE sweep. Do not trust any hand-written list.

REPO-TOPOLOGY.md (2026-08-09) lists checkouts that no longer exist and misses six that do.
The owner's list of nine and REPO-TOPOLOGY's nine are DIFFERENT sets. So enumerate by
measurement: walk the filesystem for every .git, resolve each to its object store and origin,
and keep the ones that belong to agent-skills-toolchain.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SSOT = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/ssot")
ROOTS = ["C:/Users/Prekzursil", "D:/"]
SKIP = {
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "AppData",
    "$Recycle.Bin",
    "Windows",
    "Program Files",
    "Program Files (x86)",
    ".cache",
    "site-packages",
    "System Volume Information",
    ".ruff_cache",
    ".pytest_cache",
    "OneDrive",
}
MAXDEPTH = 7


def git(repo: str, *a: str) -> str:
    p = subprocess.run(
        ["git", "-C", repo, *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout.strip() if p.returncode == 0 else ""


found = []
for root in ROOTS:
    if not Path(root).exists():
        continue
    base_depth = root.rstrip("/").count("/")
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        d = dirpath.replace("\\", "/")
        if d.count("/") - base_depth > MAXDEPTH:
            dirnames[:] = []
            continue
        dirnames[:] = [x for x in dirnames if x not in SKIP]
        if ".git" in dirnames or ".git" in filenames:
            found.append(d)
            dirnames[:] = [x for x in dirnames if x != ".git"]

print(f"filesystem sweep: {len(found)} git checkouts found under {ROOTS}")

TARGET = "agent-skills-toolchain"
matches = []
for path in found:
    origin = git(path, "config", "--get", "remote.origin.url")
    common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if TARGET not in origin.lower() and TARGET not in common.lower():
        continue
    dotgit = Path(path) / ".git"
    matches.append(
        {
            "path": path,
            "dotgit": "DIR" if dotgit.is_dir() else "FILE",
            "git_common_dir": common.replace("\\", "/"),
            "origin": origin,
            "branch": git(path, "rev-parse", "--abbrev-ref", "HEAD"),
            "head": git(path, "rev-parse", "HEAD"),
            "dirty": len(
                [
                    x
                    for x in git(path, "status", "--porcelain", "-uall").splitlines()
                    if x.strip()
                ]
            ),
        }
    )

stores: dict[str, list[str]] = {}
for m in matches:
    stores.setdefault(m["git_common_dir"].lower(), []).append(m["path"])

print(f"\ncheckouts of {TARGET}: {len(matches)}  across {len(stores)} object stores\n")
for store, paths in sorted(stores.items(), key=lambda kv: -len(kv[1])):
    print(f"STORE {store}   ({len(paths)} checkout(s))")
    for p in sorted(paths):
        m = next(x for x in matches if x["path"] == p)
        print(f"   {m['dotgit']:5} {p:52} [{m['branch']}] dirty={m['dirty']}")
    print()

# store-level worktree registration vs reality (stale admin entries)
print("=" * 78)
print("worktree registrations per store (prunable = registered but gone)")
for store in stores:
    rep = next(p for p in stores[store])
    wl = git(rep, "worktree", "list", "--porcelain")
    entries = [
        ln.split(" ", 1)[1] for ln in wl.splitlines() if ln.startswith("worktree ")
    ]
    print(f"\n  STORE {store}")
    for e in entries:
        ok = Path(e).exists()
        print(f"    {'OK  ' if ok else 'GONE'} {e}")
    pr = subprocess.run(
        ["git", "-C", rep, "worktree", "prune", "--dry-run", "-v"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    print(f"    prune --dry-run: {pr if pr else '(nothing to prune)'}")

out = {
    "all_git_checkouts_scanned": len(found),
    "matches": matches,
    "stores": {k: v for k, v in stores.items()},
}
with open(SSOT / "full-sweep.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, indent=2)
print(f"\nwrote {SSOT / 'full-sweep.json'}")
