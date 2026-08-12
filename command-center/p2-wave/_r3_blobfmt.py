"""CI-parity check: run the PINNED ruff over the STORED BLOBS of the files this lane committed.

A local green proves nothing about CI when the worktree is CRLF and the blob is LF (ruff can make
different decisions on the two forms). Blobs are read with `git ls-files -s` + `git cat-file -p`
and written into a scratch directory INSIDE the repo so `ruff.toml` still applies -- a bare temp
dir would silently use ruff's defaults and manufacture a false red.

Control: a deliberately mis-formatted copy must be reported as needing reformatting in the same
run, or the tool's silence on the real files measures nothing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
SCRATCH = REPO / "command-center/p2-wave/_r3_blobfmt_tmp"
RUFF = ["uvx", "ruff@0.15.17"]

FILES = [
    "command-center/ready_units.py",
    "command-center/p2-wave/_build_AUD0021.py",
    "command-center/p2-wave/_build_AUD0006.py",
    "command-center/p2-wave/_r3_blast.py",
    "command-center/p2-wave/_r3_rank.py",
    "command-center/p2-wave/_r3_rows.py",
    "command-center/p2-wave/_r3_blockers.py",
    "command-center/p2-wave/_r3_verify_committed.py",
    "command-center/p2-wave/_r3_annotate.py",
    "command-center/p2-wave/_r3_mk_text_fixtures.py",
    "command-center/p2-wave/_r3_probe_rows.py",
    "command-center/p2-wave/_r3_probe_textgate.py",
    "command-center/p2-wave/_r3_probe_registry.py",
]


def run(args):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True)


if SCRATCH.exists():
    shutil.rmtree(SCRATCH)
SCRATCH.mkdir(parents=True)

wrote, crlf_total = [], 0
for rel in FILES:
    ls = run(["git", "ls-files", "-s", "--", rel]).stdout.split()
    if not ls:
        print(f"  {rel}: NOT TRACKED -- skipped")
        continue
    blob = subprocess.run(
        ["git", "cat-file", "-p", ls[1]], cwd=REPO, capture_output=True
    ).stdout
    crlf_total += blob.count(b"\r\n")
    out = SCRATCH / Path(rel).name
    out.write_bytes(blob)
    wrote.append(out)

# CONTROL: a known-bad copy in the same run.
bad = SCRATCH / "zz_control_badformat.py"
bad.write_bytes(b"x  =    1\ndef  f( a ):\n  return   a\n")

r = run(RUFF + ["format", "--check", str(SCRATCH.relative_to(REPO))])
out = (r.stdout or "") + (r.stderr or "")
ctl_fired = "zz_control_badformat.py" in out
real_bad = [w.name for w in wrote if w.name in out]
print(out.strip()[-1200:])
print(f"\nblobs checked: {len(wrote)}  CRLF bytes in blobs: {crlf_total}")
print(f"CONTROL mis-formatted file reported: {ctl_fired}")
print(f"REAL files needing reformat: {real_bad}")

lint = run(RUFF + ["check", str(SCRATCH.relative_to(REPO))])
lout = (lint.stdout or "") + (lint.stderr or "")
real_lint = [w.name for w in wrote if w.name in lout]
print(f"lint findings on real blobs: {real_lint or 'none'}")

shutil.rmtree(SCRATCH)
ok = ctl_fired and not real_bad and not real_lint and crlf_total == 0
print(
    "SUCCESS:r3-blobfmt every committed blob is ruff-clean under the CI pin, and the control fired"
    if ok
    else "FAILED:r3-blobfmt see above"
)
sys.exit(0 if ok else 1)
