"""BUILD R1 -- run the CI ruff gate against the HEAD BLOBS, not the worktree.

WHY: the worktree is a moving target (sibling lanes are writing right now -- the repo-wide
"would reformat" count moved 61 -> 66 between two runs minutes apart, and three casualty
files flipped state mid-measurement). A worktree reading is therefore not reproducible and
cannot support a claim about CI.

CI checks out git blobs on Linux. On THIS box git converts LF -> CRLF on checkout (git
itself warns "LF will be replaced by CRLF the next time Git touches it"), so a
`git worktree add` would hand back CRLF and measure the wrong bytes. `git cat-file --batch`
returns the raw stored blob. `git archive` is the one that re-applies EOL conversion -- not
used here.

ruff.toml is copied to the temp root: without it ruff defaults to line-length 88 instead of
this repo's config and manufactures a false red.

CONTROL (both states): one known-clean blob is also written MANGLED into a second tree; the
harness must report it dirty. If the mangled tree comes back clean the harness is inert.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
PIN = ["uvx", "ruff@0.15.17"]
OUT = os.path.join(ROOT, "command-center/slop-report/_b3_head_blob_gate.out.json")


def tracked_py(rev="HEAD"):
    r = subprocess.run(
        ["git", "-C", ROOT, "ls-tree", "-r", "--name-only", rev],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [p for p in r.stdout.splitlines() if p.endswith(".py")]


def batch_blobs(paths, rev="HEAD"):
    """One `git cat-file --batch` process -> {path: raw bytes}."""
    stdin = "".join(f"{rev}:{p}\n" for p in paths).encode("utf-8")
    proc = subprocess.run(
        ["git", "-C", ROOT, "cat-file", "--batch"], input=stdin, capture_output=True
    )
    data = proc.stdout
    out, pos, i = {}, 0, 0
    while pos < len(data) and i < len(paths):
        nl = data.index(b"\n", pos)
        header = data[pos:nl].decode("utf-8", "replace")
        parts = header.rsplit(" ", 2)
        if len(parts) != 3 or parts[1] != "blob":
            pos = nl + 1
            i += 1
            continue
        size = int(parts[2])
        body = data[nl + 1 : nl + 1 + size]
        out[paths[i]] = body
        pos = nl + 1 + size + 1  # trailing newline
        i += 1
    return out


def materialise(files, tmp):
    shutil.copyfile(os.path.join(ROOT, "ruff.toml"), os.path.join(tmp, "ruff.toml"))
    for rel, data in files.items():
        dst = os.path.join(tmp, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as fh:
            fh.write(data)


def run(args, cwd):
    r = subprocess.run(
        [*PIN, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout + r.stderr


def main():
    rev = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    paths = tracked_py(rev)
    blobs = batch_blobs(paths, rev)
    out = {
        "rev": rev,
        "tracked_py_count": len(paths),
        "blobs_read": len(blobs),
        "total_crlf_in_blobs": sum(b.count(b"\r\n") for b in blobs.values()),
    }

    tmp = tempfile.mkdtemp(prefix="headgate_")
    try:
        materialise(blobs, tmp)
        rc_l, t_l = run(["check", ".", "--output-format=concise"], tmp)
        rc_f, t_f = run(["format", "--check", "."], tmp)
        lint = [
            x.strip()
            for x in t_l.splitlines()
            if ":" in x and x.strip() and "warning" not in x.lower()
        ]
        fmt = sorted(
            line.split("Would reformat:", 1)[1].strip().replace("\\", "/")
            for line in t_f.splitlines()
            if "Would reformat:" in line
        )
        out["gate_lint_format"] = {
            "ruff_check_rc": rc_l,
            "ruff_check_tail": t_l.strip().splitlines()[-3:],
            "ruff_check_findings": [x for x in lint if not x.startswith("Found ")][:40],
            "ruff_format_rc": rc_f,
            "ruff_format_would_reformat": fmt,
            "ruff_format_n": len(fmt),
            "ruff_format_tail": t_f.strip().splitlines()[-1:],
        }
        out["verdict"] = (
            "HEAD is CI-RED on gate-lint-format"
            if (rc_l or rc_f)
            else "HEAD is CI-GREEN on gate-lint-format"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- CONTROL --------------------------------------------------------------------------
    victim = next(p for p in paths if p == "ci/check_skill_dual_write.py")
    tmp2 = tempfile.mkdtemp(prefix="headgate_ctl_")
    try:
        materialise({victim: blobs[victim].replace(b"import ", b"import  ", 1)}, tmp2)
        rc_bad, t_bad = run(["format", "--check", "."], tmp2)
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)
    tmp3 = tempfile.mkdtemp(prefix="headgate_ok_")
    try:
        materialise({victim: blobs[victim]}, tmp3)
        rc_ok, t_ok = run(["format", "--check", "."], tmp3)
    finally:
        shutil.rmtree(tmp3, ignore_errors=True)
    checks = {"clean_blob_clean": rc_ok == 0, "mangled_blob_fires": rc_bad != 0}
    out["control"] = {
        "victim": victim,
        "clean_rc": rc_ok,
        "mangled_rc": rc_bad,
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1)[:4000])
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
