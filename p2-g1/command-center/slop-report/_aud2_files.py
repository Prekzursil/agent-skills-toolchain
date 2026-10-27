"""AUDIT R2 probe 2: Test-Path every file the builder claimed, and check
whether it is TRACKED (a file that exists only on this disk is exactly the
bucket-(b) defect the lane exists to fix).

CONTROL: the existence detector is run against a path that certainly does not
exist; it must report missing there. The tracked detector is run against a
path that exists untracked (this very probe before it is committed) and must
report tracked=False.
"""

import json
import os
import subprocess

REPO = "C:/Users/Prekzursil/source/ast-integrate"
S = "command-center/slop-report/"

CLAIMED_MODIFIED = [
    S + "_b1_control.py",
    S + "_b1_control.out.json",
    S + "SLOP-BUILD-R1.md",
]
CLAIMED_CREATED = [
    S + "SLOP-BUILD-R2.md",
    S + "_r2_d2_reproduce.py",
    S + "_r2_d2_reproduce.out.json",
    S + "_r2_fix_verify.py",
    S + "_r2_fix_verify.out.json",
    S + "_r2_gate_now.py",
    S + "_r2_gate_now.out.json",
    S + "_r2_bucket_c.py",
    S + "_r2_bucket_c.out.json",
    S + "_r2_blast_reconcile.py",
    S + "_r2_blast_reconcile.out.json",
    S + "_r2_postcommit.py",
    S + "_r2_frozen.py",
    S + "_r2_frozen.out.json",
    S + "_r2_predcheck.py",
    S + "_r2_predcheck.out.json",
    S + "_r2_postgate_before.out.json",
    S + "_r2_postgate_after.out.json",
    S + "_r2_msg_a.txt",
    S + "_r2_msg_b.txt",
    S + "_r2_msg_c.txt",
    S + "_r2_msg_d.txt",
    S + "_r2_msg_e.txt",
    S + "_r2_msg_f.txt",
]
CLAIMED_CARRIED = [
    S + "_AUDIT-SLOP-R1.json",
    S + "_VERIFY-SLOP-R1.json",
]


def git(*a):
    r = subprocess.run(
        ["git", "-C", REPO, *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


rc, out, _ = git("ls-tree", "-r", "--name-only", "HEAD")
tracked = set(x.strip() for x in out.splitlines() if x.strip())

res = {"probe": "_aud2_files", "head": git("rev-parse", "HEAD")[1].strip()}


def check(paths, label):
    rows = []
    for p in paths:
        full = os.path.join(REPO, p)
        rows.append(
            {
                "path": p,
                "exists_on_disk": os.path.isfile(full),
                "tracked_at_head": p in tracked,
                "bytes": os.path.getsize(full) if os.path.isfile(full) else None,
            }
        )
    res[label] = rows
    return rows


m = check(CLAIMED_MODIFIED, "claimed_modified")
c = check(CLAIMED_CREATED, "claimed_created")
k = check(CLAIMED_CARRIED, "claimed_carried_named")

# the 12 aud/ver probe pairs + 3 msg files claimed carried
carried_glob = sorted(
    p
    for p in tracked
    if p.startswith(S)
    and (
        os.path.basename(p).startswith("_aud") or os.path.basename(p).startswith("_ver")
    )
)
res["carried_aud_ver_tracked"] = carried_glob
res["carried_aud_ver_count"] = len(carried_glob)

missing = [r["path"] for r in (m + c + k) if not r["exists_on_disk"]]
untracked = [r["path"] for r in (m + c + k) if not r["tracked_at_head"]]
res["missing_on_disk"] = missing
res["exists_but_untracked"] = untracked

# ---- CONTROLS -------------------------------------------------------------
bogus = S + "_zzz_definitely_absent_" + "a7f31c9e" + ".py"
res["control_absent_path"] = {
    "path": bogus,
    "exists_on_disk": os.path.isfile(os.path.join(REPO, bogus)),
    "detector_reports_missing": not os.path.isfile(os.path.join(REPO, bogus)),
}
this_probe = S + "_aud2_files.py"
res["control_untracked_path"] = {
    "path": this_probe,
    "exists_on_disk": os.path.isfile(os.path.join(REPO, this_probe)),
    "tracked_at_head": this_probe in tracked,
    "detector_reports_untracked": (this_probe not in tracked),
}

ok = (
    not missing
    and not untracked
    and res["control_absent_path"]["detector_reports_missing"]
    and res["control_untracked_path"]["exists_on_disk"]
    and res["control_untracked_path"]["detector_reports_untracked"]
)
res["verdict"] = "ALL-CLAIMED-FILES-EXIST-AND-TRACKED" if ok else "FILE-CLAIM-PROBLEM"
res["ok"] = ok

with open(
    os.path.join(REPO, S, "_aud2_files.out.json"), "w", encoding="utf-8", newline="\n"
) as fh:
    json.dump(res, fh, indent=2)

print(
    json.dumps(
        {
            k2: v
            for k2, v in res.items()
            if k2
            not in (
                "claimed_modified",
                "claimed_created",
                "claimed_carried_named",
                "carried_aud_ver_tracked",
            )
        },
        indent=2,
    )
)
print(
    "counts: modified=%d created=%d carried_named=%d aud_ver_tracked=%d"
    % (len(m), len(c), len(k), len(carried_glob))
)
