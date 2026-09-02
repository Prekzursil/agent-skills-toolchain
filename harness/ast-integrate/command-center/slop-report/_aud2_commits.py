"""AUDIT R2 probe 1: commit integrity.

Independently re-measures the builder's six claimed commits:
  - exists, is ancestor of HEAD
  - numstat file count / insertions / deletions
  - foreign paths (anything outside command-center/slop-report/)
  - tracked deletions (status D)
Also measures whether command-center/slop-report is currently dirty.

CONTROL: the foreign-path detector is run against a KNOWN-FOREIGN commit
(a sibling commit that touches docs/ or command-center/hook-audit/) and must
report foreign>0 there; otherwise the detector is inert and its zero on my
lane's commits proves nothing.
"""

import json
import subprocess
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
SCOPE = "command-center/slop-report/"
CLAIMED = {
    "383ad694": (6, 540, 11),
    "25ddfe61": (8, 968, 6),
    "ebcd0bc1": (29, 3057, 0),
    "43cb7a62": (10, 634, 26),
    "2ab835c3": (4, 173, 3),
    "1a3f09f4": (2, 56, 7),
}


def git(*args):
    r = subprocess.run(
        ["git", "-C", REPO, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


def measure(rev):
    rc, out, _ = git("show", "--numstat", "--format=", rev)
    if rc != 0:
        return None
    files, ins, dels = 0, 0, 0
    foreign = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, d, path = parts
        files += 1
        ins += 0 if a == "-" else int(a)
        dels += 0 if d == "-" else int(d)
        if not path.startswith(SCOPE):
            foreign.append(path)
    # tracked deletions (status letter D)
    rc2, out2, _ = git("show", "--name-status", "--format=", rev)
    deleted = [ln.split("\t", 1)[1] for ln in out2.splitlines() if ln.startswith("D\t")]
    rc3, out3, _ = git("merge-base", "--is-ancestor", rev, "HEAD")
    return {
        "rev": rev,
        "files": files,
        "insertions": ins,
        "deletions_lines": dels,
        "foreign_paths": foreign,
        "tracked_deletions": deleted,
        "is_ancestor_of_head": rc3 == 0,
    }


res = {"probe": "_aud2_commits", "scope": SCOPE}
rc, head, _ = git("rev-parse", "HEAD")
res["head"] = head.strip()

rows = []
mismatches = []
for rev, (cf, ci, cd) in CLAIMED.items():
    m = measure(rev)
    if m is None:
        rows.append({"rev": rev, "error": "MISSING"})
        mismatches.append(f"{rev}: commit missing")
        continue
    m["claimed"] = {"files": cf, "insertions": ci, "deletions": cd}
    m["matches_claim"] = (m["files"], m["insertions"], m["deletions_lines"]) == (
        cf,
        ci,
        cd,
    )
    if not m["matches_claim"]:
        mismatches.append(
            f"{rev}: measured {m['files']}/{m['insertions']}/{m['deletions_lines']} "
            f"claimed {cf}/{ci}/{cd}"
        )
    if m["foreign_paths"]:
        mismatches.append(f"{rev}: FOREIGN {m['foreign_paths']}")
    if m["tracked_deletions"]:
        mismatches.append(f"{rev}: DELETIONS {m['tracked_deletions']}")
    if not m["is_ancestor_of_head"]:
        mismatches.append(f"{rev}: NOT ancestor of HEAD")
    rows.append(m)

res["commits"] = rows
res["mismatches"] = mismatches

# ---- CONTROL: detector must FIRE on a known-foreign commit -----------------
# 7aa86f16 is a sibling commit (docs: repair a decapitated README section)
ctrl = measure("7aa86f16")
res["control_known_foreign_commit"] = {
    "rev": "7aa86f16",
    "foreign_count": len(ctrl["foreign_paths"]) if ctrl else None,
    "sample": (ctrl["foreign_paths"][:3] if ctrl else None),
    "detector_fires": bool(ctrl and ctrl["foreign_paths"]),
}
# CONTROL 2: deletion detector must fire on a commit that deletes something
rc, out, _ = git("log", "--diff-filter=D", "--format=%H", "-3", "--", ".")
del_commits = out.split()
fired = False
for c in del_commits:
    m = measure(c)
    if m and m["tracked_deletions"]:
        fired = True
        res["control_known_deletion_commit"] = {
            "rev": c,
            "deleted_sample": m["tracked_deletions"][:3],
        }
        break
res["control_deletion_detector_fires"] = fired

# ---- current dirtiness of my scope ----------------------------------------
rc, out, _ = git("status", "--porcelain", "--", SCOPE)
res["slop_report_dirty_entries"] = [ln for ln in out.splitlines() if ln.strip()]
res["slop_report_dirty_count"] = len(res["slop_report_dirty_entries"])

# tracked file count under scope
rc, out, _ = git("ls-tree", "-r", "--name-only", "HEAD", "--", SCOPE)
res["tracked_files_under_scope_at_head"] = len(
    [x for x in out.splitlines() if x.strip()]
)

ok = not mismatches and res["control_known_foreign_commit"]["detector_fires"] and fired
res["verdict"] = "COMMIT-INTEGRITY-OK" if ok else "COMMIT-INTEGRITY-PROBLEM"
res["ok"] = ok

with open(
    "C:/Users/Prekzursil/source/ast-integrate/command-center/slop-report/_aud2_commits.out.json",
    "w",
    encoding="utf-8",
    newline="\n",
) as fh:
    json.dump(res, fh, indent=2)
print(json.dumps(res, indent=2))
sys.exit(0 if ok else 1)
