"""Normalize the auditor's own files to LF before committing.

The audit found that my own probe files failed `ruff format --check` at the CI
pin -- which is precisely the defect class this lane exists to prevent
(committing unformatted files under command-center/ turns main red). Fixing my
own output before committing, and re-measuring, is the only honest move.

Reads and writes with newline="" so a CRLF/LF conversion is deliberate and
visible, never an accident of the io layer.
"""

import glob
import os

REPO = "C:/Users/Prekzursil/source/ast-integrate"
PAT = os.path.join(REPO, "command-center/slop-report/_aud2_*.py")

for p in sorted(glob.glob(PAT)):
    with open(p, "rb") as fh:
        raw = fh.read()
    crlf = raw.count(b"\r\n")
    fixed = raw.replace(b"\r\n", b"\n")
    if fixed != raw:
        with open(p, "wb") as fh:
            fh.write(fixed)
    print(
        f"{os.path.basename(p):32s} crlf_before={crlf:4d} crlf_after={fixed.count(chr(13).encode() + chr(10).encode())}"
    )
