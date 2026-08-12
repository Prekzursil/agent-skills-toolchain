"""AUDIT: reconstruct the artifact state tally AT THE BUILDER'S BASELINE (03e565ea~1).

Reads git BLOBS, not the worktree, so sibling lanes landing work afterwards cannot skew it.
"""
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REV = "03e565ea~1"


def git(*a):
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


cat_blob = git("cat-file", "-p", f"{REV}:command-center/WORK-UNIT-CATALOG.json")
CAT = json.loads(cat_blob.stdout)
units = CAT["work_units"]
print(f"  catalog units at {REV}: {len(units)}")

tally, present, ids = {}, 0, []
for u in units:
    op = u.get("output_path")
    if not op:
        continue
    r = git("cat-file", "-p", f"{REV}:{op}")
    if r.returncode != 0 or not r.stdout.strip():
        continue
    present += 1
    ids.append(u["id"])
    try:
        d = json.loads(r.stdout)
    except Exception:
        tally["<unparseable>"] = tally.get("<unparseable>", 0) + 1
        continue
    st = d.get("state") if isinstance(d, dict) else None
    key = st if isinstance(st, str) else "<no-state-field>"
    tally[key] = tally.get(key, 0) + 1

print(f"  artifacts tracked & non-empty at baseline : {present}   (builder: 44)")
print(f"  state tally at baseline                   : {tally}")
print(f"     (builder claimed {{'BLOCKED': 42, 'FAILED': 1, '<no-state-field>': 1}})")
notdone = sum(v for k, v in tally.items() if k.upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
print(f"  self-declared NOT-done at baseline        : {notdone} of {present}   (builder: 43 of 44)")
