# CNF-0015 independent reviewer, step 1: catalog requirement + chain of custody.
# Fresh-context reviewer (claude). Writes findings to stdout; caller tees to raw evidence.
import hashlib
import json
import os
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\agent-skills-toolchain")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
RECEIPT = REPO / "command-center" / "confirmation" / "CNF-0015-blocker-repro.json"

print("=== STEP 1a: catalog entry CNF-0015 ===")
cat = json.loads(CATALOG.read_text(encoding="utf-8"))
# tolerate either a list of units or a dict with a 'units' key
units = cat.get("work_units") if isinstance(cat, dict) else cat
if isinstance(units, dict):
    units = list(units.values())
entry = None
for u in units:
    if isinstance(u, dict) and (
        u.get("id") == "CNF-0015" or u.get("unit_id") == "CNF-0015"
    ):
        entry = u
        break
if entry is None:
    print("FAILED:step1 CNF-0015 entry not found in catalog")
else:
    s = json.dumps(entry, indent=1, ensure_ascii=False)
    print(s[:4000])
    if len(s) > 4000:
        print(f"...[truncated, total {len(s)} chars]")

print("\n=== STEP 1b: chain of custody - sha256/bytes vs receipt ===")
rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
all_ok = True
for art in rec.get("artifacts", []):
    p = REPO / art["path"]
    if not p.is_file():
        print(f"MISSING {art['path']}")
        all_ok = False
        continue
    b = p.read_bytes()
    sha = hashlib.sha256(b).hexdigest()
    ok = sha == art["sha256"] and len(b) == art["bytes"]
    all_ok = all_ok and ok
    print(
        f"{'MATCH' if ok else 'MISMATCH'} {art['path']} bytes={len(b)}/{art['bytes']} sha={sha[:16]}.. vs {art['sha256'][:16]}.."
    )
print(f"CHAIN_OF_CUSTODY: {'all-match' if all_ok else 'BROKEN'}")

print("\n=== STEP 1c: repo/git state + live-doc presence ===")
git_dir = REPO / ".git"
print(
    f".git exists: {git_dir.exists()} ({'file(worktree)' if git_dir.is_file() else 'dir' if git_dir.is_dir() else 'none'})"
)
probes = REPO / "command-center" / "p2-wave" / "probes" / "CNF-0015"
for root, dirs, files in os.walk(probes):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in sorted(files):
        fp = Path(root) / f
        print(f"probe-file {fp.relative_to(REPO).as_posix()} {fp.stat().st_size}B")

# live docs 07/13/17 - check candidates WITHOUT recursion (RAM discipline)
candidates = [
    REPO / "13-ARCHITECTURE-CANDIDATES.md",
    REPO / "command-center" / "13-ARCHITECTURE-CANDIDATES.md",
    Path(r"C:\Users\Prekzursil\.claude\harness-restore-20260806"),
]
hr = Path(r"C:\Users\Prekzursil\.claude\harness-restore-20260806")
if hr.is_dir():
    print("harness-restore-20260806 exists; top-level entries (max 30):")
    for i, child in enumerate(sorted(hr.iterdir())):
        if i >= 30:
            print("  ...[capped at 30]")
            break
        print(f"  {child.name}{'/' if child.is_dir() else ''}")
else:
    print("harness-restore-20260806: NOT PRESENT")
for c in candidates[:2]:
    print(
        f"live-doc candidate {c.relative_to(REPO).as_posix() if c.is_relative_to(REPO) else c}: {c.exists()}"
    )
