"""B9: re-measure the blob-verification recipe before rewriting a skill body that teaches it.

Two claims are under test, and they point in OPPOSITE directions, so a probe that could not
distinguish them would be useless:

  (1) `git archive` applies export-time EOL conversion on Windows -> hands back CRLF, so it is
      the WRONG way to check "what does CI check out".
  (2) `git show <rev>:<path>` does NOT -> hands back the stored LF blob, so it IS correct.
      (The program floor asserted (2) was also CRLF; the correction says that is false.)

CONTROL: all routes must be byte-identical AFTER LF-normalisation.  If they are not, the files
differ in CONTENT and any line-ending conclusion drawn from them would be an artifact.
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
from io import BytesIO
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
TARGETS = [
    ".agents/skills/two-tier-verify/SKILL.md",
    "ci/check_skill_deploy_drift.py",
]


def git(args: list[str]) -> bytes:
    r = subprocess.run(["git"] + args, capture_output=True, cwd=str(REPO))
    if r.returncode != 0:
        raise SystemExit(f"git {args} failed: {r.stderr[:300]!r}")
    return r.stdout


def norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


rc = 0
for rel in TARGETS:
    show = git(["show", f"HEAD:{rel}"])
    oid = git(["rev-parse", f"HEAD:{rel}"]).decode().strip()
    cat = git(["cat-file", "-p", oid])
    tarbytes = git(["archive", "HEAD", "--", rel])
    with tarfile.open(fileobj=BytesIO(tarbytes)) as tf:
        member = tf.extractfile(tf.getmember(rel))
        arch = member.read() if member else b""
    wt = (REPO / rel).read_bytes()

    rows = [
        ("git show <rev>:<path>", show),
        ("git cat-file -p <oid>", cat),
        ("git archive + tar -x", arch),
        ("working tree", wt),
    ]
    print(f"=== {rel}")
    for tag, data in rows:
        # NOTE: an earlier revision wrote `data.count(b'CRLF'[:0])`, i.e. count of the EMPTY
        # bytestring, which returns len+1 -- it printed "CRLF=7488" for a 7487-byte file.  A
        # count larger than the payload is a self-contradicting output, so it was a detector
        # failure, not a finding; fixed here rather than read.
        crlf = data.count(b"\r\n")
        print(f"   {tag:24} bytes={len(data):>7}  CRLF={crlf}")
    same = {norm(d) for _, d in rows}
    ok = len(same) == 1
    print(f"   CONTROL all-routes-identical-after-LF-normalisation: {ok}")
    if not ok:
        rc = 1
sys.exit(rc)
