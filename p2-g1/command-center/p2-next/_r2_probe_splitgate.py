"""ROUND-2: does the lane's OTHER published command have the same non-idempotence defect?

The auditor confirmed it for vendor_satisfiability.py. split_review_gate.py is the other command in
the round-1 reproduce block and it also writes a COMMITTED artifact. Same class, so measure it
rather than assume: hash the artifact, run the script, hash again, and restore the committed bytes
if it drifted. Restore is verified by content hash, not by `git status` (which reports a stale " M"
under sibling index contention on this tree).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ART = "command-center/p2-next/REVIEW-GATE-SPLIT.json"
SCRIPT = "command-center/p2-next/split_review_gate.py"


def sh(*a, **kw):
    return subprocess.run(
        list(a), cwd=REPO, capture_output=True, text=True, encoding="utf-8", **kw
    )


head = sh("git", "rev-parse", f"HEAD:{ART}").stdout.strip()
before = sh("git", "hash-object", ART).stdout.strip()
print(f"artifact HEAD blob   : {head[:12]}")
print(f"artifact before run  : {before[:12]}  (== HEAD: {before == head})")

r = sh(sys.executable, SCRIPT)
tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-3:]
print(f"\nrun rc={r.returncode}")
for ln in tail:
    print(f"   {ln}")

after = sh("git", "hash-object", ART).stdout.strip()
drift = after != before
print(f"\nartifact after run   : {after[:12]}  DRIFTED={drift}")

if drift:
    blob = subprocess.run(
        ["git", "show", f"HEAD:{ART}"], cwd=REPO, capture_output=True
    ).stdout
    (REPO / ART).write_bytes(blob)
    restored = sh("git", "hash-object", ART).stdout.strip()
    print(f"RESTORED committed bytes: {restored[:12]}  match={restored == head}")
    if restored != head:
        print("FAILED:r2-probe-splitgate could not restore")
        raise SystemExit(1)

print(
    "\nVERDICT: split_review_gate.py "
    + (
        "ALSO rewrites its committed artifact on re-run"
        if drift
        else "is idempotent on re-run"
    )
)
print("SUCCESS:r2-probe-splitgate")
