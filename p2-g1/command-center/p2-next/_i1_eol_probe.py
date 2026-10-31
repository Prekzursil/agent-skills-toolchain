"""Byte-level EOL probe for the two files this lane must edit.

windows-shell.md 8b: a text-mode read/write turns a 3-line append into a whole-file diff.
Measure before writing, so the append can be made in the file's own line ending.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

for rel in (
    ".github/workflows/no-runtime-junk.yml",
    "command-center/CROSS-VENDOR-RAIL-STATUS.md",
    "command-center/p2-next/VENDOR-SATISFIABILITY.json",
):
    b = (REPO / rel).read_bytes()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n")
    print(
        f"{rel}\n  bytes={len(b)}  LF={lf}  CRLF={crlf}  bare-LF={lf - crlf}  tail={b[-14:]!r}"
    )
