"""Fresh-clone verification: does the STORED BLOB reproduce the receipt's elided digest?

A working-tree green does not imply a clone green. Git may normalise EOLs on the way into
the object store, and the receipts' elided sha256 was computed over LF bytes written with
newline="\\n". If the blob differs, a reviewer who clones the repo cannot reproduce the
digest and the receipt's own verification recipe fails for them.

Uses `git cat-file -p`, which returns the STORED bytes. Deliberately NOT `git archive`,
which applies export-time EOL conversion and hands back CRLF on Windows.

Control: also reports the worktree bytes and CRLF counts for both, so a difference is
visible rather than assumed.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
TARGETS = [
    "command-center/casualty/ADV-0021-install-path-stride-threat-model.json",
    "command-center/casualty/ADV-0022-declared-permission-escape.json",
]


def blob_bytes(rev: str, path: str) -> bytes:
    return subprocess.run(["git", "cat-file", "-p", f"{rev}:{path}"],
                          cwd=REPO, capture_output=True, check=True).stdout


fail = 0
for rel in TARGETS:
    wt = (REPO / rel).read_bytes()
    try:
        bl = blob_bytes("HEAD", rel)
    except subprocess.CalledProcessError as e:
        print(f"=== {rel}\n  NOT IN HEAD: {e}")
        fail = 1
        continue

    declared = re.search(rb'"sha256":\s*"([0-9a-f]{64})"', bl).group(1).decode()
    elided_blob = hashlib.sha256(
        re.sub(declared.encode(), b"0" * 64, bl, count=1)).hexdigest()
    elided_wt = hashlib.sha256(
        re.sub(declared.encode(), b"0" * 64, wt, count=1)).hexdigest()

    print(f"=== {rel}")
    crlf = bytes([13, 10])
    print(f"  worktree bytes {len(wt):>8}  CRLF {wt.count(crlf):>5}")
    print(f"  blob     bytes {len(bl):>8}  CRLF {bl.count(crlf):>5}")
    print(f"  declared elided sha256 : {declared}")
    print(f"  recomputed from BLOB   : {elided_blob}  MATCH={elided_blob == declared}")
    print(f"  recomputed from WORKTREE: {elided_wt}  MATCH={elided_wt == declared}")
    if elided_blob != declared:
        print("  FAILED:blob-parity a fresh clone CANNOT reproduce this receipt's digest")
        fail = 1
    else:
        print("  SUCCESS:blob-parity a fresh clone reproduces the declared digest")

sys.exit(fail)
