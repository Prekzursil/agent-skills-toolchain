"""Independent re-measurement of skills/ vs .agents/skills/ divergence.

Deliberately NOT reusing the builder's probe. Two mechanically different
sources are compared:
  A) filesystem: directories directly under each root that contain SKILL.md
  B) git ls-tree at a pinned rev: same, from the object store

Detector controls:
  - inject a synthetic name into each side and require BOTH difference arms
    to fire (a set difference that can only return [] is inert)
  - plausibility floor: abort if either root yields < 50 names (collapsed glob)
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")


def fs_names(rel):
    d = ROOT / rel
    if not d.is_dir():
        return None
    return {p.name for p in d.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}


def git_names(rev, rel):
    out = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", rev, "--", rel + "/"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    names = set()
    prefix = rel + "/"
    for line in out:
        if not line.endswith("/SKILL.md"):
            continue
        if not line.startswith(prefix):
            continue
        tail = line[len(prefix):]
        parts = tail.split("/")
        if len(parts) == 2:  # <name>/SKILL.md exactly one level deep
            names.add(parts[0])
    return names


def report(tag, a, b):
    only_a = sorted(a - b)
    only_b = sorted(b - a)
    both = a & b
    print(f"[{tag}] skills/={len(a)} .agents/skills/={len(b)} both={len(both)}")
    print(f"[{tag}] ONLY-in-skills/ ({len(only_a)}): {only_a}")
    print(f"[{tag}] ONLY-in-.agents/skills/ ({len(only_b)}): {only_b}")
    return only_a, only_b, both


fs_a = fs_names("skills")
fs_b = fs_names(".agents/skills")
if fs_a is None or fs_b is None:
    print("FAILED: a root is missing")
    sys.exit(2)
if len(fs_a) < 50 or len(fs_b) < 50:
    print(f"FAILED plausibility floor: {len(fs_a)} / {len(fs_b)}")
    sys.exit(2)

oa, ob, both = report("FS-worktree", fs_a, fs_b)

for rev in ("84bf3a33", "HEAD"):
    ga = git_names(rev, "skills")
    gb = git_names(rev, ".agents/skills")
    if len(ga) < 50 or len(gb) < 50:
        print(f"FAILED plausibility floor at {rev}: {len(ga)} / {len(gb)}")
        sys.exit(2)
    report(f"GIT-{rev}", ga, gb)

# CONTROL: both difference arms must be able to fire
ca = set(fs_a) | {"__synthetic_only_left__"}
cb = set(fs_b) | {"__synthetic_only_right__"}
left = sorted(ca - cb)
right = sorted(cb - ca)
fired_left = "__synthetic_only_left__" in left
fired_right = "__synthetic_only_right__" in right
print(f"[CONTROL] left-arm fires={fired_left} right-arm fires={fired_right}")
if not (fired_left and fired_right):
    print("FAILED: detector control did not fire")
    sys.exit(2)

print("SUCCESS:verify-divergence")
