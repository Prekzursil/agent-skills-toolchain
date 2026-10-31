"""AUDIT housekeeping: undo the artifact mutations MY OWN re-runs caused.

Re-running the builder's quoted evidence scripts REWRITES committed deliverables. `git checkout`
timed out against a contended index, so restore by writing the HEAD blob back byte-for-byte in
BINARY mode (no newline translation), then verify each file is clean again.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FILES = [
    "command-center/p2-next/REVIEW-AUD-0006.json",
    "command-center/p2-next/REVIEW-PREDICATE-PROBE.json",
    "command-center/p2-next/REVIEW-THREE-RESOLVED.json",
    "command-center/p2-next/REVIEW-TST0350-NC2.json",
]

for rel in FILES:
    r = subprocess.run(
        ["git", "cat-file", "-p", f"HEAD:{rel}"], cwd=REPO, capture_output=True
    )
    if r.returncode != 0:
        print(f"SKIP {rel}: {r.stderr.decode(errors='replace')[:120]}")
        continue
    dst = REPO / rel
    before = dst.read_bytes()
    if before == r.stdout:
        print(f"already-identical {rel}")
        continue
    with open(dst, "wb") as fh:
        fh.write(r.stdout)
    print(f"restored {rel}: {len(before)} -> {len(r.stdout)} bytes")

st = subprocess.run(
    ["git", "status", "--porcelain", "--", *FILES],
    cwd=REPO,
    capture_output=True,
    text=True,
    timeout=180,
)
print("\ngit status for the four:", repr(st.stdout) or "(clean)")
print("CLEAN" if not st.stdout.strip() else "STILL DIRTY -- investigate")
