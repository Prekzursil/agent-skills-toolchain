"""P11 - W2-07 follow-through: of the files still untracked at HEAD in the five Wave-2 directories,
how many are gitignored SCRATCH (safe) versus untracked-and-not-ignored (a `git clean -xfd` /
worktree reset still destroys them)?

Also re-measures the forged-workflow id collision at every named commit in the fix chain, so the
"3 -> 2 -> 0" story is checked against real bytes rather than an implementer's summary.
"""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
DIRS = [
    "platform/workflows",
    "platform/architecture",
    "platform/lib/workflows",
    "platform/lib/foundry",
    "command-center/schema",
]
OUT: dict[str, object] = {}


def sh(args: list[str]) -> str:
    return subprocess.run(
        args, cwd=str(REPO), capture_output=True, text=True, check=False
    ).stdout


census = {}
for d in DIRS:
    disk = sorted(
        str(p.relative_to(REPO)).replace("\\", "/")
        for p in (REPO / d).rglob("*")
        if p.is_file()
    )
    tracked = set(x for x in sh(["git", "ls-files", "--", d]).split("\n") if x.strip())
    untracked = [f for f in disk if f not in tracked]
    ignored: set[str] = set()
    # check-ignore in chunks; it exits 1 when nothing matches, which is not an error here
    for i in range(0, len(untracked), 100):
        chunk = untracked[i : i + 100]
        r = subprocess.run(
            ["git", "check-ignore", *chunk],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        ignored.update(x for x in r.stdout.split("\n") if x.strip())
    unprotected = [f for f in untracked if f not in ignored]
    census[d] = {
        "on_disk": len(disk),
        "tracked": len(tracked),
        "untracked": len(untracked),
        "untracked_but_gitignored_scratch": len(ignored),
        "untracked_and_NOT_ignored": len(unprotected),
        "unprotected_sample": unprotected[:10],
    }
OUT["W2_07_tracking_census_at_worktree"] = census
OUT["W2_07_totals"] = {
    "on_disk": sum(v["on_disk"] for v in census.values()),
    "tracked": sum(v["tracked"] for v in census.values()),
    "untracked_and_NOT_ignored": sum(
        v["untracked_and_NOT_ignored"] for v in census.values()
    ),
}

# ---- forged id collision across the whole fix chain -------------------------------------------
CHAIN = [
    ("0aa6f8fa", "W2 end"),
    ("5e54207e", "W3 first"),
    ("964cfa05", "W3 forge-id fix (first copy)"),
    ("29f4c72a", "pinned ground-truth commit"),
    ("c1c51852", "W3 forge-id fix (second copy)"),
    ("04e4736c", "HEAD / W3 end"),
]


def forged_ids(rev: str) -> dict[str, list[str]]:
    names = [
        p
        for p in sh(
            ["git", "ls-tree", "-r", "--name-only", rev, "--", "platform/workflows"]
        ).split("\n")
        if p.endswith(".json")
    ]
    by: dict[str, list[str]] = defaultdict(list)
    for p in names:
        r = subprocess.run(
            ["git", "cat-file", "-p", f"{rev}:{p}"],
            cwd=str(REPO),
            capture_output=True,
            check=False,
        )
        if r.returncode:
            continue
        try:
            d = json.loads(r.stdout.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and "dsl_version" in d and "stages" in d:
            by[str(d.get("id"))].append(p)
    return {k: sorted(v) for k, v in by.items() if len(v) > 1}


chain = {}
for rev, label in CHAIN:
    dups = forged_ids(rev)
    chain[f"{rev} ({label})"] = {
        "colliding_ids": len(dups),
        "detail": dups,
    }
OUT["W2_08_W3_02_id_collision_chain"] = chain

# working tree, same structural rule
by_wt: dict[str, list[str]] = defaultdict(list)
for p in (REPO / "platform/workflows").rglob("*.json"):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        continue
    if isinstance(d, dict) and "dsl_version" in d and "stages" in d:
        by_wt[str(d.get("id"))].append(str(p.relative_to(REPO)).replace("\\", "/"))
OUT["W2_08_worktree_now"] = {k: v for k, v in by_wt.items() if len(v) > 1}

dest = REPO / "command-center" / "P11-TRACKING-AND-IDS.json"
dest.write_text(json.dumps(OUT, indent=2), encoding="utf-8")
print(json.dumps(OUT, indent=2))
print(f"SUCCESS:p11-tracking {dest}")
