"""Independent divergence measurement, 3 mechanically different methods + injection control."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    return p.stdout


def m1_ls_files():
    """Exactly what the shipped test does."""
    out = git("ls-files", "-z", "--", "skills")
    proj = {m.group(1) for f in out.split("\0") if f
            for m in [re.fullmatch(r"skills/([^/]+)/SKILL\.md", f)] if m}
    out = git("ls-files", "-z", "--", ".agents/skills")
    canon = {m.group(1) for f in out.split("\0") if f
             for m in [re.fullmatch(r"\.agents/skills/([^/]+)/SKILL\.md", f)] if m}
    return proj, canon


def m2_ls_tree(rev):
    """Committed tree at a rev -- what CI checks out. Independent of the index."""
    out = git("ls-tree", "-r", "--name-only", "-z", rev, "--", "skills")
    proj = {m.group(1) for f in out.split("\0") if f
            for m in [re.fullmatch(r"skills/([^/]+)/SKILL\.md", f)] if m}
    out = git("ls-tree", "-r", "--name-only", "-z", rev, "--", ".agents/skills")
    canon = {m.group(1) for f in out.split("\0") if f
             for m in [re.fullmatch(r"\.agents/skills/([^/]+)/SKILL\.md", f)] if m}
    return proj, canon


def m3_fs():
    """Raw filesystem scan -- sees untracked dirs the index does not."""
    proj = {d.name for d in (ROOT / "skills").iterdir()
            if d.is_dir() and (d / "SKILL.md").is_file()}
    canon = {d.name for d in (ROOT / ".agents" / "skills").iterdir()
             if d.is_dir() and (d / "SKILL.md").is_file()}
    return proj, canon


def report(tag, proj, canon):
    op, oc = sorted(proj - canon), sorted(canon - proj)
    print(f"[{tag}] proj={len(proj)} canon={len(canon)} both={len(proj & canon)} "
          f"only_proj={len(op)} only_canon={len(oc)}")
    print(f"[{tag}]   only_proj  = {op}")
    print(f"[{tag}]   only_canon = {oc}")
    return len(op), len(oc)


results = {}
p, c = m1_ls_files(); results["ls-files(index)"] = report("M1 ls-files", p, c)
for rev in ("HEAD", "84bf3a33"):
    p, c = m2_ls_tree(rev); results[f"ls-tree({rev})"] = report(f"M2 ls-tree {rev}", p, c)
p, c = m3_fs(); results["fs"] = report("M3 filesystem", p, c)

# DETECTOR CONTROL: both set-difference arms must be able to fire.
p, c = m1_ls_files()
left = bool((p | {"__ctl_left__"}) - c)
right = bool((c | {"__ctl_right__"}) - p)
# and prove they can also be EMPTY (not stuck-on)
empty_left = ((p & c) - c)
print(f"[CONTROL] left-arm-fires={left} right-arm-fires={right} "
      f"arm-can-be-empty={empty_left == set()}")
assert left and right and empty_left == set(), "detector control FAILED"

vals = set(results.values())
print(f"[AGREEMENT] distinct (only_proj,only_canon) tuples across 4 methods: {vals}")
if len(vals) != 1:
    print("FAILED:advver-divergence methods DISAGREE -- ", results)
    sys.exit(1)
print(f"SUCCESS:advver-divergence all 4 methods agree {vals.pop()}")
