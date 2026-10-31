"""SLOP lane measurement. Read-only. Classifies every non-.git path as
tracked / ignored / untracked-unignored, and sizes the buckets."""

import json
import os
import subprocess
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
OUT = REPO + "/command-center/slop-report/_slop_measure.out.json"


def git(*args):
    r = subprocess.run(
        ["git", "-C", REPO] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


def lines(s):
    return [x for x in s.replace("\r\n", "\n").split("\n") if x.strip()]


res = {}

# --- 1. tracked set -------------------------------------------------------
rc, out, err = git("ls-files")
tracked = set(lines(out))
res["tracked_count"] = len(tracked)
res["tracked_rc"] = rc

# --- 2. untracked, NOT ignored -------------------------------------------
rc, out, err = git("ls-files", "--others", "--exclude-standard")
untracked = lines(out)
res["untracked_unignored_count"] = len(untracked)

# --- 3. untracked AND ignored --------------------------------------------
rc, out, err = git("ls-files", "--others", "--ignored", "--exclude-standard")
ignored = lines(out)
res["ignored_count"] = len(ignored)

# --- DETECTOR CONTROL A: the three sets must be disjoint and cover the tree
overlap = set(untracked) & set(ignored)
res["control_untracked_ignored_overlap"] = len(overlap)
res["control_tracked_in_untracked"] = len(tracked & set(untracked))


def size(p):
    fp = os.path.join(REPO, p)
    try:
        return os.path.getsize(fp)
    except OSError:
        return -1


def bucketize(paths):
    d = {}
    for p in paths:
        top = p.split("/")[0]
        second = "/".join(p.split("/")[:2]) if "/" in p else "(root file)"
        d.setdefault(second, {"n": 0, "bytes": 0, "top": top})
        d[second]["n"] += 1
        s = size(p)
        if s > 0:
            d[second]["bytes"] += s
    return dict(sorted(d.items(), key=lambda kv: -kv[1]["bytes"]))


res["untracked_by_dir"] = bucketize(untracked)
res["ignored_by_dir"] = bucketize(ignored)
res["untracked_files"] = sorted((p, size(p)) for p in untracked)
res["untracked_total_bytes"] = sum(max(0, size(p)) for p in untracked)
res["ignored_total_bytes"] = sum(max(0, size(p)) for p in ignored)

# --- 4. the naming-convention gap: _x.out.json vs _x_out.json ------------
gap = [
    p
    for p in untracked
    if p.split("/")[-1].startswith("_") and (".out." in p or ".err." in p)
]
res["naming_gap_dot_out"] = sorted(gap)
res["naming_gap_count"] = len(gap)
# control: the underscore form IS ignored
underscore_form = [
    p for p in ignored if p.endswith("_out.json") or p.endswith("_out.err")
]
res["control_underscore_out_is_ignored_count"] = len(underscore_form)
res["control_underscore_out_sample"] = underscore_form[:5]

# --- 5. command-center subdir census -------------------------------------
cc = {}
ccroot = os.path.join(REPO, "command-center")
for name in sorted(os.listdir(ccroot)):
    fp = os.path.join(ccroot, name)
    if os.path.isdir(fp):
        n = 0
        b = 0
        for dp, dn, fn in os.walk(fp):
            for f in fn:
                n += 1
                try:
                    b += os.path.getsize(os.path.join(dp, f))
                except OSError:
                    pass
        cc[name] = {"files": n, "bytes": b}
res["command_center_dirs"] = dict(sorted(cc.items(), key=lambda kv: -kv[1]["bytes"]))

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(res, fh, indent=1, sort_keys=False)

print("tracked:", res["tracked_count"])
print(
    "untracked-unignored:",
    res["untracked_unignored_count"],
    res["untracked_total_bytes"],
    "B",
)
print("ignored:", res["ignored_count"], res["ignored_total_bytes"], "B")
print(
    "CONTROL overlap untracked&ignored (must be 0):",
    res["control_untracked_ignored_overlap"],
)
print("CONTROL tracked&untracked (must be 0):", res["control_tracked_in_untracked"])
print("naming-gap .out./.err. untracked:", res["naming_gap_count"])
print(
    "CONTROL underscore _out form ignored:",
    res["control_underscore_out_is_ignored_count"],
)
print("--- untracked by dir ---")
for k, v in list(res["untracked_by_dir"].items()):
    print(f"  {k:45s} {v['n']:5d} files {v['bytes']:12d} B")
print("--- command-center dirs ---")
for k, v in res["command_center_dirs"].items():
    print(f"  {k:25s} {v['files']:6d} files {v['bytes']:12d} B")
sys.exit(0)
