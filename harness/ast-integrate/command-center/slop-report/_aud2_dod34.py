"""AUDIT R2 probe 5: DoD-3 (bucket-c regenerator) and DoD-4 (frozen evidence),
both measured by the AUDITOR, not by re-running the builder's probes.

DoD-3 -- the published bucket-(c) regenerating command must actually work.
  I delete the artifact MYSELF, assert it is gone, run the PUBLISHED command,
  and require: rc 0, artifact back, byte-identical within the run, and the
  command left no tracked file dirty. (Round 1's published command exited rc 1
  and dirtied a tracked file -- that is the defect under re-test.)

DoD-4 -- frozen evidence untouched.
  Method differs from the builder's: instead of hashing files, I ask git
  directly whether the pathspec has ANY diff across the lane's range, and
  whether any commit in that range touches it. Plus the working tree.
  CONTROL: the same differ is pointed at a path that IS known to have changed
  in the range (command-center/slop-report). It must report changed there --
  otherwise a clean reading on the frozen dirs measures nothing. This is the
  control shape this estate got wrong before ("3 == 3 on both sides").
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
LANE_PARENT = "61e69cf2"
FROZEN = ["command-center/casualty/probes", "command-center/p2-wave/probes"]
KNOWN_CHANGED = "command-center/slop-report"
PYCACHE = "command-center/slop-report/__pycache__"
REGEN_CMD = ["python", "command-center/slop-report/_b1_control.py"]


def git(*a):
    r = subprocess.run(
        ["git", "-C", REPO, *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


def dirty(pathspec):
    rc, out, _ = git("status", "--porcelain", "--", pathspec)
    return [ln for ln in out.splitlines() if ln.strip()]


def changed_in_range(pathspec):
    rc, out, _ = git("diff", "--name-only", f"{LANE_PARENT}..HEAD", "--", pathspec)
    return [ln for ln in out.splitlines() if ln.strip()]


def commits_touching(pathspec):
    rc, out, _ = git("log", "--format=%H", f"{LANE_PARENT}..HEAD", "--", pathspec)
    return [ln for ln in out.splitlines() if ln.strip()]


def sha_dir(rel):
    root = os.path.join(REPO, rel)
    acc = {}
    for dp, _dn, fn in os.walk(root):
        for f in sorted(fn):
            p = os.path.join(dp, f)
            with open(p, "rb") as fh:
                acc[os.path.relpath(p, root).replace("\\", "/")] = hashlib.sha256(
                    fh.read()
                ).hexdigest()[:16]
    return acc


res = {
    "probe": "_aud2_dod34",
    "lane_parent": LANE_PARENT,
    "head": git("rev-parse", "HEAD")[1].strip(),
}

# ---------------- DoD-4 -----------------------------------------------------
frozen_rows = {}
for f in FROZEN:
    frozen_rows[f] = {
        "n_files_on_disk": len(sha_dir(f)),
        "changed_in_range": changed_in_range(f),
        "commits_touching_in_range": commits_touching(f),
        "dirty_worktree": dirty(f),
    }
    frozen_rows[f]["untouched"] = (
        not frozen_rows[f]["changed_in_range"]
        and not frozen_rows[f]["commits_touching_in_range"]
        and not frozen_rows[f]["dirty_worktree"]
    )
res["frozen"] = frozen_rows
res["all_frozen_untouched"] = all(v["untouched"] for v in frozen_rows.values())

# CONTROL: the SAME differ must FIRE on a known-changed path
ctrl_changed = changed_in_range(KNOWN_CHANGED)
ctrl_commits = commits_touching(KNOWN_CHANGED)
res["control_known_changed_path"] = {
    "path": KNOWN_CHANGED,
    "n_changed_files": len(ctrl_changed),
    "n_commits": len(ctrl_commits),
    "differ_fires": bool(ctrl_changed) and bool(ctrl_commits),
}
# CONTROL 2: the on-disk hasher must be non-constant
probe_files = sha_dir(FROZEN[0])
res["control_hasher_nonconstant"] = {
    "n_distinct_hashes": len(set(probe_files.values())),
    "n_files": len(probe_files),
    "nonconstant": len(set(probe_files.values())) > 1,
}

# ---------------- DoD-3 -----------------------------------------------------
d3 = {"published_command": " ".join(REGEN_CMD)}
full_pycache = os.path.join(REPO, PYCACHE)
d3["existed_before"] = os.path.isdir(full_pycache)
before_files = sorted(os.listdir(full_pycache)) if d3["existed_before"] else []
before_hashes = {
    f: hashlib.sha256(open(os.path.join(full_pycache, f), "rb").read()).hexdigest()[:16]
    for f in before_files
}
d3["files_before"] = before_hashes

dirty_before = dirty("command-center/slop-report")
d3["tracked_dirty_before"] = [x for x in dirty_before if not x.startswith("??")]

if d3["existed_before"]:
    shutil.rmtree(full_pycache)
d3["absent_after_delete"] = not os.path.isdir(full_pycache)

p = subprocess.run(
    REGEN_CMD,
    cwd=REPO,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
d3["regen_rc"] = p.returncode
d3["regen_stderr_tail"] = p.stderr.strip()[-300:]
try:
    d3["regen_verdict"] = json.loads(p.stdout)["verdict"]
except Exception:  # noqa: BLE001
    d3["regen_verdict"] = "UNPARSEABLE"

d3["present_after_regen"] = os.path.isdir(full_pycache)
after_files = sorted(os.listdir(full_pycache)) if d3["present_after_regen"] else []
after_hashes = {
    f: hashlib.sha256(open(os.path.join(full_pycache, f), "rb").read()).hexdigest()[:16]
    for f in after_files
}
d3["files_after"] = after_hashes
d3["byte_identical_within_run"] = before_hashes == after_hashes

dirty_after = dirty("command-center/slop-report")
d3["tracked_dirty_after"] = [x for x in dirty_after if not x.startswith("??")]
d3["command_left_tree_clean"] = d3["tracked_dirty_after"] == d3["tracked_dirty_before"]
d3["is_pycache_tracked"] = bool(git("ls-files", "--", PYCACHE)[1].strip())
d3["checks"] = {
    "existed_before": d3["existed_before"],
    "absent_after_delete": d3["absent_after_delete"],
    "present_after_regen": d3["present_after_regen"],
    "byte_identical": d3["byte_identical_within_run"],
    "rc_zero": d3["regen_rc"] == 0,
    "left_tree_clean": d3["command_left_tree_clean"],
    "artifact_is_untracked_scratch": not d3["is_pycache_tracked"],
}
d3["pass"] = all(d3["checks"].values())
res["dod3_bucket_c"] = d3

ok = (
    res["all_frozen_untouched"]
    and res["control_known_changed_path"]["differ_fires"]
    and res["control_hasher_nonconstant"]["nonconstant"]
    and d3["pass"]
)
res["verdict"] = "DOD3-AND-DOD4-CONFIRMED" if ok else "DOD-PROBLEM"
res["ok"] = ok

with open(
    os.path.join(REPO, "command-center/slop-report/_aud2_dod34.out.json"),
    "w",
    encoding="utf-8",
    newline="\n",
) as fh:
    json.dump(res, fh, indent=2)
print(json.dumps(res, indent=2))
sys.exit(0 if ok else 1)
