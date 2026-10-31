"""BUILD-R1 pre-flight: will ci_gate's inventory invariant hold on a FRESH CLONE?

ci_gate globs ``*.py`` in its own directory. On a runner that directory contains exactly the
COMMITTED files -- not the working tree. So a probe named in EXCLUDED but never committed is a
"ghost" and turns CI red, and a probe committed but not named is "unclassified" and does the
same. Working-tree green does not imply clone green.

This computes the post-commit tracked set (currently tracked, plus the files this round
intends to add) and runs ci_gate.classify() against it BEFORE the commit.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import ci_gate  # noqa: E402

INTENT_ADD = [
    "ci_gate.py",
    "_b1_gate_runner.py",
    "_b2_slowgate_probe.py",
    "_b3_portability.py",
    "_b4_read_i1.py",
    "_b5_tiktoken.py",
    "_b7_normalize_lf.py",
    "_b8_redproof.py",
    "_b9_preflight.py",
    "_i1_ci_portability.py",
    "_r5_grounding_probe.py",
]

tracked = subprocess.run(
    ["git", "ls-files", "docs/rule-audit"],
    cwd=REPO,
    capture_output=True,
    text=True,
    check=True,
).stdout.split()
tracked_py = {Path(p).name for p in tracked if p.endswith(".py")}

post_commit = tracked_py | set(INTENT_ADD)
unclassified, ghosts = ci_gate.classify(post_commit)

on_disk = {p.name for p in HERE.glob("*.py")}
never_committed = sorted(on_disk - post_commit)

print(f"tracked .py now          : {len(tracked_py)}")
print(f"intending to add         : {len(INTENT_ADD)}")
print(f"post-commit tracked .py  : {len(post_commit)}")
print(f"on disk right now        : {len(on_disk)}")
print()
print(f"UNCLASSIFIED (would fail CI): {unclassified or 'none'}")
print(f"GHOSTS      (would fail CI): {ghosts or 'none'}")
print(f"on disk but NOT committed  : {never_committed or 'none'}")
print()
if unclassified or ghosts:
    print("FAILED:b9_preflight the commit as planned would turn CI red")
    raise SystemExit(1)
print(
    f"SUCCESS:b9_preflight post-commit inventory is complete ({len(post_commit)} files)"
)
