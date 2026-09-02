"""Is AUD-0030's module_count=679 explained by tracked-vs-untracked, or is 13 modules missing?

H1 = the unit lost 13 modules.
H2 = the unit measured the TRACKED tree / an earlier snapshot; sibling lanes have since added
     untracked .py files under tools/.
These look different: under H2 the extra files are untracked and/or newer than the unit's run.
"""

import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def rel(p):
    return str(p.relative_to(ROOT)).replace("\\", "/")


def keep(r):
    return not ({"node_modules", "vendor"} & set(r.split("/")))


disk = sorted(rel(p) for p in (ROOT / "tools").rglob("*.py") if keep(rel(p)))
tracked = sorted(
    f for f in git("ls-files", "tools").splitlines() if f.endswith(".py") and keep(f)
)
untracked = sorted(set(disk) - set(tracked))
deleted = sorted(set(tracked) - set(disk))
print(f"disk (non-vendored)      : {len(disk)}")
print(f"git-tracked (non-vendored): {len(tracked)}")
print(f"untracked-on-disk         : {len(untracked)}")
print(f"tracked-but-absent        : {len(deleted)}")
print("TARGET (unit's module_count): 679")
for lbl, n in (
    ("disk", len(disk)),
    ("tracked", len(tracked)),
    ("tracked+untracked", len(disk)),
):
    print(f"   {lbl:<18} = {n} {'<== MATCHES' if n == 679 else ''}")
print("\nuntracked .py under tools/ (the candidate explanation):")
for u in untracked:
    print("   +", u)
print("\ncommits adding .py under tools/ in the last day:")
print(
    git(
        "log",
        "--oneline",
        "--since=2026-08-11",
        "--diff-filter=A",
        "--name-only",
        "--",
        "tools/*.py",
        "tools/**/*.py",
    )[:2000]
)

res = {
    "disk_non_vendored": len(disk),
    "git_tracked_non_vendored": len(tracked),
    "untracked_count": len(untracked),
    "untracked_paths": untracked,
    "unit_module_count": 679,
    "verdict": (
        "REVIEWER-INSTRUMENT/time-indexed"
        if len(tracked) == 679 or len(disk) - len(untracked) == 679
        else "UNRESOLVED-13-MODULE-DELTA"
    ),
}
print(f"\nVERDICT: {res['verdict']}")
(ROOT / "command-center/p2-next/REVIEW-AUD0030-MODULES.json").write_text(
    json.dumps(res, indent=2), encoding="utf-8"
)
print("SUCCESS:aud0030-modules")
