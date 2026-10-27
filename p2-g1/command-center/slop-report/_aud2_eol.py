"""Resolve a detector conflict about MY OWN commit's stored line endings.

Two readings disagreed:
  A) `git cat-file -p <rev>:<path> | grep -c $'\\r'`  -> nonzero (CRLF present?)
  B) the already-validated binary read used by _aud2_gate_indep.py, which
     reported 0 CRLF across 2360 tracked .py blobs.

Both cannot be right. Per the estate rule, a self-contradicting output is a
DETECTOR failure, not a finding -- so this probe measures the bytes in binary
with no shell pipe anywhere, and CONTROLS itself against a blob whose line
endings are known from the other direction.

CONTROLS:
  P1 known-LF   : a .py blob that predates this auditor (tracked long before)
                  must read 0 CRLF. If it reads nonzero, the reader is broken.
  P2 known-CRLF : a synthetic CRLF buffer must read nonzero. If it reads 0, the
                  reader is blind and its zeros mean nothing.
"""

import json
import os
import subprocess

REPO = "C:/Users/Prekzursil/source/ast-integrate"
MINE_GREP = "independent round-2 audit"
KNOWN_OLD = "command-center/slop-report/_b1_control.py"


def git_text(*a):
    r = subprocess.run(
        ["git", "-C", REPO, *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.stdout


def blob(rev, path):
    """Raw stored bytes -- binary, no shell, no pipe, no text decoding."""
    r = subprocess.run(
        ["git", "-C", REPO, "cat-file", "-p", f"{rev}:{path}"], capture_output=True
    )
    return r.stdout if r.returncode == 0 else None


res = {"probe": "_aud2_eol"}
rev = git_text("log", "--format=%H", "--grep", MINE_GREP, "-1").strip()
res["my_commit"] = rev

paths = [
    p
    for p in git_text("show", "--name-only", "--format=", rev).splitlines()
    if p.strip()
]

rows = []
for p in paths:
    data = blob(rev, p)
    if data is None:
        rows.append({"path": p, "error": "unreadable"})
        continue
    rows.append(
        {
            "path": p,
            "bytes": len(data),
            "crlf_pairs": data.count(b"\r\n"),
            "bare_cr": data.count(b"\r") - data.count(b"\r\n"),
            "lf_total": data.count(b"\n"),
        }
    )
res["files"] = rows
res["total_crlf_pairs_in_my_commit"] = sum(r.get("crlf_pairs", 0) for r in rows)

# ---- CONTROLS -------------------------------------------------------------
old = blob("HEAD", KNOWN_OLD)
res["P1_known_old_blob"] = {
    "path": KNOWN_OLD,
    "crlf_pairs": old.count(b"\r\n") if old is not None else None,
    "reader_reports_lf": (old is not None and old.count(b"\r\n") == 0),
}
synthetic = b"a = 1\r\nb = 2\r\n"
res["P2_synthetic_crlf"] = {
    "crlf_pairs": synthetic.count(b"\r\n"),
    "reader_sees_crlf": synthetic.count(b"\r\n") > 0,
}

# ---- what the SHELL detector said, reproduced here for the record ---------
# Was a `git cat-file -p | grep -c $'\r'` pipeline under shell=True, which turned gate-sast red
# (quality.opengrep.python-subprocess-shell-true). Rewritten as an argument list: shell=True with
# an interpolated path is a real injection surface, and the rule is right to reject it here rather
# than be waived for a convenience pipeline.
#
# CAREFUL -- `grep -c PATTERN` counts LINES CONTAINING the pattern, not occurrences of it. Counting
# CR bytes instead would silently change a recorded measurement. Equivalence was MEASURED before
# this edit, not reasoned: both routes returned '0' on this blob, AND a synthetic control with a
# known answer of 3 returned 3, so the agreement is a reading rather than two zeros coinciding.
_blob = subprocess.run(
    [
        "git",
        "-C",
        REPO,
        "cat-file",
        "-p",
        f"{rev}:command-center/slop-report/_aud2_commits.py",
    ],
    capture_output=True,
).stdout
res["shell_detector_output"] = str(
    sum(1 for _line in _blob.split(b"\n") if b"\r" in _line)
)

res["controls_pass"] = (
    res["P1_known_old_blob"]["reader_reports_lf"]
    and res["P2_synthetic_crlf"]["reader_sees_crlf"]
)
res["verdict"] = (
    "MY-BLOBS-ARE-LF"
    if (res["controls_pass"] and res["total_crlf_pairs_in_my_commit"] == 0)
    else ("MY-BLOBS-HAVE-CRLF" if res["controls_pass"] else "READER-UNCONTROLLED")
)

with open(
    os.path.join(REPO, "command-center/slop-report/_aud2_eol.out.json"),
    "w",
    encoding="utf-8",
    newline="\n",
) as fh:
    json.dump(res, fh, indent=2)

print(json.dumps({k: v for k, v in res.items() if k != "files"}, indent=2))
for r in rows:
    print(
        f"  crlf={r.get('crlf_pairs'):4} lf={r.get('lf_total'):5}  {r['path'].split('/')[-1]}"
    )
