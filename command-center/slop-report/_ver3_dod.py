"""Adversarial verifier probe 3: execute the four DoD items and the D2 receipt claim.

Nothing here is read from a report. Every verdict is a measurement taken now.

Controls:
  H1 hasher non-constant  -- a constant-returning hasher would make "all bytes match" a
                             guaranteed PASS under both hypotheses. Proven by re-hashing
                             (equal) and hashing a mutated copy (differs), with n_files > 0.
  H2 delete/regen middle  -- the INTERMEDIATE ABSENCE is asserted. Without it, "the file is
                             there afterwards" cannot be told apart from "it was never gone".
  H3 restore verified     -- after executing _b1_control.py (which rewrites a COMMITTED file),
                             the bytes are restored and re-compared to the HEAD blob.
"""

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

R = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate")
PRELANE = "899ff779"
FROZEN = ["command-center/casualty/probes", "command-center/p2-wave/probes"]
res = {}


def git(*a, timeout=300):
    p = subprocess.run(
        ["git", "-C", str(R), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return p.returncode, p.stdout, p.stderr


def blob(path):
    p = subprocess.run(
        ["git", "-C", str(R), "cat-file", "-p", f"HEAD:{path}"], capture_output=True
    )
    return p.stdout if p.returncode == 0 else None


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


# ---------------- DoD2: bucket (b) committed, not deleted ----------------
names = [
    n
    for n in git("ls-tree", "-r", "--name-only", "HEAD", "--", "command-center")[
        1
    ].split()
    if n.count("/") == 1 and n.startswith("command-center/_") and n.endswith(".py")
]
differ, missing, tot = [], [], 0
for n in names:
    b = blob(n)
    tot += len(b or b"")
    f = R / n
    if not f.exists():
        missing.append(n)
    elif f.read_bytes() != b:
        differ.append(n)
on_disk = sorted(
    p.name
    for p in (R / "command-center").iterdir()
    if p.is_file() and p.name.startswith("_") and p.name.endswith(".py")
)
dels = {}
for c in ("f5b596e6", "fa87d1a2", "ebe02d62"):
    dels[c] = len(
        [
            x
            for x in git("show", "--diff-filter=D", "--name-only", "--format=", c)[
                1
            ].split()
            if x
        ]
    )
res["DoD2"] = {
    "n_tracked_root_probes": len(names),
    "tracked_blob_bytes": tot,
    "missing_on_disk": len(missing),
    "worktree_bytes_differ_from_blob": len(differ),
    "differing": differ[:5],
    "n_root_probes_on_disk_now": len(on_disk),
    "tracked_deletions_per_commit": dels,
    "pass": len(names) == 45 and not missing and not differ and sum(dels.values()) == 0,
}

# ---------------- DoD4: frozen evidence, four independent signals ----------------
f = {}
f["S1_commits_touching_since_prelane"] = len(
    [
        x
        for x in git("log", "--oneline", f"{PRELANE}..HEAD", "--", *FROZEN)[
            1
        ].splitlines()
        if x
    ]
)
f["S2_diff_prelane_to_head"] = len(
    [
        x
        for x in git("diff", "--name-only", PRELANE, "HEAD", "--", *FROZEN)[1].split()
        if x
    ]
)
f["S3_dirty_lines"] = len(
    [x for x in git("status", "--porcelain", "--", *FROZEN)[1].splitlines() if x]
)
f["S4_lane_commits_touching"] = {
    c: len(
        [
            x
            for x in git("show", "--name-only", "--format=", c)[1].split()
            if "casualty/probes" in x or "p2-wave/probes" in x
        ]
    )
    for c in ("f5b596e6", "fa87d1a2", "ebe02d62")
}
counts, digest = {}, {}
for d in FROZEN:
    fs = sorted(p for p in (R / d).rglob("*") if p.is_file())
    counts[d] = len(fs)
    digest[d] = sha(b"".join(p.read_bytes() for p in fs))
f["file_counts"] = counts
f["dir_digests"] = digest
# H1 hasher control: stable re-hash equal, mutated differs, and n>0
sample = sorted((R / FROZEN[0]).rglob("*"))
sample = [p for p in sample if p.is_file()]
raw = sample[0].read_bytes()
f["H1_hasher_control"] = {
    "n_files": len(sample),
    "stable_rehash_equal": sha(raw) == sha(raw),
    "mutated_differs": sha(raw) != sha(raw + b"x"),
    "pass": len(sample) > 0 and sha(raw) == sha(raw) and sha(raw) != sha(raw + b"x"),
}
f["pass"] = (
    f["S1_commits_touching_since_prelane"] == 0
    and f["S2_diff_prelane_to_head"] == 0
    and f["S3_dirty_lines"] == 0
    and sum(f["S4_lane_commits_touching"].values()) == 0
    and f["H1_hasher_control"]["pass"]
)
res["DoD4"] = f

# ---------------- D2: does the committed control receipt survive re-execution? ----------------
RECEIPT = "command-center/slop-report/_b1_control.out.json"
orig_blob = blob(RECEIPT)
before = json.loads(orig_blob.decode())
p = subprocess.run(
    [sys.executable, str(R / "command-center/slop-report/_b1_control.py")],
    capture_output=True,
    text=True,
    cwd=str(R),
    timeout=900,
)
after_bytes = (R / RECEIPT).read_bytes()
after = json.loads(after_bytes.decode())
# restore the committed bytes and PROVE the restore
(R / RECEIPT).write_bytes(orig_blob)
restored_ok = (R / RECEIPT).read_bytes() == orig_blob
dirty_after = len(
    [x for x in git("status", "--porcelain", "--", RECEIPT)[1].splitlines() if x]
)
res["D2_receipt_reexecution"] = {
    "committed_quiet_citer_count": before["quiet_citer_count"],
    "committed_verdict": before["verdict"],
    "reexec_rc": p.returncode,
    "reexec_quiet_citer_count": after["quiet_citer_count"],
    "reexec_verdict": after["verdict"],
    "reexec_fire_citer_count": after["fire_citer_count"],
    "committed_fire_citer_count": before["fire_citer_count"],
    "receipt_bytes_changed_by_rerun": after_bytes != orig_blob,
    "H3_restore_verified": restored_ok and dirty_after == 0,
    "self_refutes": before["verdict"] == "PASS" and after["verdict"] != "PASS",
}

# ---------------- DoD3: bucket (c) delete -> absent -> regen byte-identical ----------------
PYC = R / "command-center/slop-report/__pycache__"


def pycstate():
    if not PYC.exists():
        return {"exists": False, "n": 0, "hashes": {}}
    fs = sorted(PYC.glob("*"))
    return {
        "exists": True,
        "n": len(fs),
        "hashes": {x.name: sha(x.read_bytes()) for x in fs},
    }


s_before = pycstate()
shutil.rmtree(PYC, ignore_errors=True)
s_gone = pycstate()
rc2 = subprocess.run(
    [sys.executable, str(R / "command-center/slop-report/_b1_control.py")],
    capture_output=True,
    text=True,
    cwd=str(R),
    timeout=900,
).returncode
(R / RECEIPT).write_bytes(orig_blob)  # the regen command rewrites it again
s_after = pycstate()
res["DoD3"] = {
    "regen_command": "python command-center/slop-report/_b1_control.py",
    "before": s_before,
    "after_delete": s_gone,
    "after_regen": s_after,
    "H2_intermediate_absence_checked": s_gone["n"] == 0 and not s_gone["exists"],
    "regen_rc": rc2,
    "byte_identical": s_before["hashes"] == s_after["hashes"] and s_before["n"] > 0,
    "regen_command_exits_nonzero": rc2 != 0,
    "regen_command_dirties_a_tracked_file": True,
    "pass": (
        s_before["n"] > 0
        and s_gone["n"] == 0
        and s_before["hashes"] == s_after["hashes"]
    ),
}

# ---------------- blast radius sanity at HEAD ----------------
cc = [
    n
    for n in git("ls-tree", "-r", "--name-only", "HEAD", "--", "command-center")[
        1
    ].split()
    if n.rsplit("/", 1)[-1].startswith("_") and n.endswith(".py")
]
res["blast_radius"] = {
    "tracked_command_center_underscore_py_at_HEAD": len(cc),
    "of_which_root": len([n for n in cc if n.count("/") == 1]),
    "of_which_nested": len([n for n in cc if n.count("/") > 1]),
}

res["final_status_dirty_slopreport_tracked"] = len(
    [
        x
        for x in git("status", "--porcelain", "--", "command-center/slop-report")[
            1
        ].splitlines()
        if x and not x.startswith("??")
    ]
)
pathlib.Path(__file__).with_suffix(".out.json").write_text(
    json.dumps(res, indent=2), encoding="utf-8", newline="\n"
)
print(json.dumps(res, indent=2)[:7000])
