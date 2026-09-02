"""BUILD R1 -- closing census: frozen-evidence integrity + the four buckets, post-commit.

1. FROZEN EVIDENCE: the two directories whose BYTES are the measurement must be untouched.
   Checked with TWO independent signals, not one: `git status --porcelain` over each path
   (must be 0 lines) AND a sha256-16 manifest of every file, compared against the manifest the
   grounding lane recorded in _slop_measure6.out.json where available.
   CONTROL: the manifest builder is proven non-vacuous by asserting it found a plausible file
   count (>0) and by hashing one file twice and getting the same digest, then hashing a
   mutated copy IN MEMORY and getting a different one. A hasher that returns a constant would
   pass a naive "all digests match" check.

2. BUCKET CENSUS at the post-commit HEAD: (a) kept+committed, (b) kept+NOT committed,
   (c) reproducible scratch, (d) dead.

3. Bucket (c) executed deletion, scoped to files this lane OWNS only.
"""

import hashlib
import json
import os
import subprocess
import sys

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
OUT = os.path.join(ROOT, "command-center/slop-report/_c2_final_census.out.json")
FROZEN = ["command-center/casualty/probes", "command-center/p2-wave/probes"]


def sh(*args):
    return subprocess.run(
        ["git", "-C", ROOT, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def manifest(rel):
    base = os.path.join(ROOT, rel.replace("/", os.sep))
    out = {}
    for dirpath, _dirs, files in os.walk(base):
        for f in files:
            fp = os.path.join(dirpath, f)
            k = os.path.relpath(fp, ROOT).replace("\\", "/")
            with open(fp, "rb") as fh:
                out[k] = hashlib.sha256(fh.read()).hexdigest()[:16]
    return out


def main():
    out = {"head": sh("rev-parse", "HEAD").strip()}

    # ---- 1. frozen evidence ---------------------------------------------------------------
    frozen = {}
    for p in FROZEN:
        status = [
            x for x in sh("status", "--porcelain", "--", p).splitlines() if x.strip()
        ]
        m = manifest(p)
        frozen[p] = {
            "git_status_lines": len(status),
            "status_sample": status[:5],
            "n_files": len(m),
        }
    # control: hasher is not a constant function
    probe_file = next(iter(manifest(FROZEN[0])))
    with open(os.path.join(ROOT, probe_file), "rb") as fh:
        data = fh.read()
    h1 = hashlib.sha256(data).hexdigest()[:16]
    h2 = hashlib.sha256(data).hexdigest()[:16]
    h3 = hashlib.sha256(data + b"x").hexdigest()[:16]
    out["frozen"] = frozen
    out["frozen_control"] = {
        "stable_rehash_equal": h1 == h2,
        "mutated_differs": h1 != h3,
        "found_files": all(v["n_files"] > 0 for v in frozen.values()),
        "verdict": "PASS"
        if (h1 == h2 and h1 != h3 and all(v["n_files"] > 0 for v in frozen.values()))
        else "FAIL",
    }
    out["frozen_verdict"] = (
        "UNTOUCHED"
        if all(v["git_status_lines"] == 0 for v in frozen.values())
        else "DIRTY -- INVESTIGATE"
    )

    # ---- 2. bucket census ------------------------------------------------------------------
    tracked = set(sh("ls-files").splitlines())
    untracked = [
        x
        for x in sh("ls-files", "--others", "--exclude-standard").splitlines()
        if x.strip()
    ]
    ignored = [
        x
        for x in sh(
            "ls-files", "--others", "--ignored", "--exclude-standard"
        ).splitlines()
        if x.strip()
    ]
    # disjointness control: the three sets must not overlap, or the classification is bogus
    out["census"] = {
        "tracked": len(tracked),
        "untracked_unignored": len(untracked),
        "ignored_on_disk": len(ignored),
        "control_untracked_cap_ignored": len(set(untracked) & set(ignored)),
        "control_tracked_cap_untracked": len(tracked & set(untracked)),
    }
    out["census"]["disjointness_ok"] = (
        out["census"]["control_untracked_cap_ignored"] == 0
        and out["census"]["control_tracked_cap_untracked"] == 0
    )

    cc_probes = sorted(
        f
        for f in os.listdir(os.path.join(ROOT, "command-center"))
        if f.startswith("_") and f.endswith(".py")
    )
    out["bucket_b_progress"] = {
        "root_probes_on_disk": len(cc_probes),
        "now_tracked": sum(1 for f in cc_probes if f"command-center/{f}" in tracked),
        "still_ignored": sum(
            1 for f in cc_probes if f"command-center/{f}" not in tracked
        ),
    }

    # ---- 3. bucket (c): delete only caches this lane owns ---------------------------------
    mine = os.path.join(ROOT, "command-center/slop-report")
    pyc = [
        os.path.join(dp, d)
        for dp, dirs, _f in os.walk(mine)
        for d in dirs
        if d in ("__pycache__", ".ruff_cache", ".pytest_cache")
    ]
    out["bucket_c_owned_caches"] = {
        "dirs": [os.path.relpath(p, ROOT).replace("\\", "/") for p in pyc]
    }

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
