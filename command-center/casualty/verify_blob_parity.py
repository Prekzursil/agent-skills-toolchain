"""Blob-parity and (with --fresh-clone) REAL fresh-clone verification of the receipts' digests.

ROUND-2 SCOPE CORRECTION, audit-confirmed. Round 1 printed "a fresh clone reproduces the
declared digest" while making no clone at all: on a clean working tree blob == worktree by
construction, so the default mode proves the STORED BLOB reproduces the digest and nothing
about a clone. The refuted sentence is recorded here rather than deleted. `--fresh-clone` now
does the real thing: `git clone` into a throwaway directory, then recompute the digest from
BOTH the clone's object store and the clone's checked-out file. The second of those is the
one that can differ -- a checkout applies EOL conversion, which is exactly the
worktree-green-vs-clone-green trap this program has already been bitten by.

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


def blob_bytes(rev: str, path: str, cwd: Path = REPO) -> bytes:
    return subprocess.run(["git", "cat-file", "-p", f"{rev}:{path}"],
                          cwd=cwd, capture_output=True, check=True).stdout


def elide_digest(raw: bytes, declared: str) -> str:
    return hashlib.sha256(re.sub(declared.encode(), b"0" * 64, raw, count=1)).hexdigest()


def fresh_clone_check() -> int:
    """Clone this repo into a throwaway directory and re-derive both digests there."""
    import shutil
    import tempfile
    bad = 0
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True, check=True).stdout.strip()
    tmp = Path(tempfile.mkdtemp(prefix="r2_fresh_clone_"))
    dest = tmp / "clone"
    try:
        url = "file:///" + str(REPO).replace("\\", "/")
        r = subprocess.run(["git", "clone", "--depth", "1", "--no-hardlinks", url, str(dest)],
                           capture_output=True, text=True)
        print("=== FRESH CLONE")
        print(f"  source      : {url}")
        print(f"  clone rc    : {r.returncode}  {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}")
        if r.returncode != 0:
            print("  FAILED:fresh-clone clone did not complete")
            return 1
        chead = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest,
                               capture_output=True, text=True, check=True).stdout.strip()
        print(f"  origin HEAD : {head}")
        print(f"  clone  HEAD : {chead}   SAME={chead == head}")
        if chead != head:
            print("  FAILED:fresh-clone the clone is not at the commit under test")
            return 1
        for rel in TARGETS:
            cb = blob_bytes("HEAD", rel, cwd=dest)
            cw = (dest / rel).read_bytes()
            declared = re.search(rb'"sha256":\s*"([0-9a-f]{64})"', cb).group(1).decode()
            d_blob, d_wt = elide_digest(cb, declared), elide_digest(cw, declared)
            crlf = bytes([13, 10])
            print(f"  --- {rel}")
            print(f"      clone blob     bytes {len(cb):>8} CRLF {cb.count(crlf):>5} "
                  f"digest MATCH={d_blob == declared}")
            print(f"      clone CHECKOUT bytes {len(cw):>8} CRLF {cw.count(crlf):>5} "
                  f"digest MATCH={d_wt == declared}")
            if d_blob != declared or d_wt != declared:
                print("      FAILED:fresh-clone a reviewer who clones this repo cannot "
                      "reproduce the declared digest")
                bad = 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SUCCESS:fresh-clone both receipts reproduce their declared digest from a clone "
          "that never saw this working tree" if not bad else "FAILED:fresh-clone")
    return bad


if "--fresh-clone" in sys.argv:
    raise SystemExit(fresh_clone_check())

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
        print("  FAILED:blob-parity the STORED BLOB at HEAD does not reproduce this digest")
        fail = 1
    else:
        print("  SUCCESS:blob-parity the STORED BLOB at HEAD reproduces the declared digest "
              "(this mode makes NO clone; run --fresh-clone for that)")

sys.exit(fail)
