"""BUILD R1 -- is main ACTUALLY red on the ruff format gate, checked against the BLOB?

A worktree `ruff format --check` can disagree with CI because the worktree may hold CRLF
while the stored blob (what CI checks out on Linux) is LF, and ruff makes different
decisions on the two forms. So: materialise each suspect file from `git cat-file -p`
(0 CRLF, unlike `git archive` which re-applies EOL conversion on Windows), mirror the
relative path, and copy ruff.toml in -- without the config ruff defaults to line-length 88
instead of this repo's setting and manufactures a false red.

CONTROL (both states): a deliberately mangled copy of an ALREADY-CLEAN tracked file must be
reported as "would reformat" by this same harness. If the mangled control comes back clean
the harness is inert and its silence proves nothing.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
PIN = ["uvx", "ruff@0.15.17"]
OUT = os.path.join(ROOT, "command-center/slop-report/_b2_blob_check.out.json")

SUSPECTS = [
    "command-center/casualty/_build_adv0021.py",
    "command-center/casualty/_build_adv0022.py",
    "command-center/casualty/_r2_patch_receipts.py",
]
CLEAN_CONTROL = "ci/check_skill_dual_write.py"  # tracked and format-clean in S2


def blob(path, rev="HEAD"):
    r = subprocess.run(
        ["git", "-C", ROOT, "cat-file", "-p", f"{rev}:{path}"], capture_output=True
    )
    if r.returncode != 0:
        return None
    return r.stdout  # raw bytes, no newline translation


def check_tree(files: dict) -> tuple[int, str]:
    """files: relpath -> raw bytes. Returns (rc, output) of `ruff format --check .`"""
    tmp = tempfile.mkdtemp(prefix="blobfmt_")
    try:
        shutil.copyfile(os.path.join(ROOT, "ruff.toml"), os.path.join(tmp, "ruff.toml"))
        for rel, data in files.items():
            dst = os.path.join(tmp, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as fh:
                fh.write(data)
        r = subprocess.run(
            [*PIN, "format", "--check", "."],
            cwd=tmp,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, r.stdout + r.stderr
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    out = {
        "rev": subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
    }

    files = {}
    meta = {}
    for p in SUSPECTS:
        b = blob(p)
        if b is None:
            meta[p] = {"error": "not in HEAD"}
            continue
        files[p] = b
        meta[p] = {
            "blob_bytes": len(b),
            "blob_crlf": b.count(b"\r\n"),
            "worktree_bytes": os.path.getsize(os.path.join(ROOT, p)),
            "worktree_crlf": open(os.path.join(ROOT, p), "rb").read().count(b"\r\n"),
        }
    out["suspects"] = meta

    rc, txt = check_tree(files)
    would = sorted(
        line.split("Would reformat:", 1)[1].strip().replace("\\", "/")
        for line in txt.splitlines()
        if "Would reformat:" in line
    )
    out["blob_check"] = {
        "rc": rc,
        "would_reformat": would,
        "n": len(would),
        "tail": txt.strip().splitlines()[-2:],
    }

    # ---- CONTROL --------------------------------------------------------------------------
    cb = blob(CLEAN_CONTROL)
    rc_clean, txt_clean = check_tree({CLEAN_CONTROL: cb})
    mangled = cb.replace(
        b"import ", b"import  ", 1
    )  # double space -> ruff must reformat
    rc_bad, txt_bad = check_tree({CLEAN_CONTROL: mangled})
    checks = {
        "clean_control_is_clean": "Would reformat" not in txt_clean,
        "mangled_control_fires": "Would reformat" in txt_bad,
        "control_bytes_differ": cb != mangled,
    }
    out["control"] = {
        "file": CLEAN_CONTROL,
        "clean_rc": rc_clean,
        "mangled_rc": rc_bad,
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }
    out["verdict"] = (
        "MAIN-IS-RED on ruff format (blob-confirmed)"
        if would
        else "MAIN-IS-GREEN on ruff format for these files"
    )

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
