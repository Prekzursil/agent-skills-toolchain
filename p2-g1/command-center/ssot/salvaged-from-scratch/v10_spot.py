"""V10: EXECUTABLE spot-check of two of the ten review notes' load-bearing claims.
Neither the builder nor the auditor executed these -- both READ the notes."""

import re
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")

# --- claim A (AUD-0030 review): "exactly 1 cycle, members
#     ['tools.crcp.crcp.sentinel', 'tools.crcp.crcp.write_path']"
a = REPO / "tools/crcp/crcp/sentinel.py"
b = REPO / "tools/crcp/crcp/write_path.py"
print("claim A -- the reviewer's Kosaraju cycle actually exists in the tree?")
for p in (a, b):
    print(f"   exists {p.relative_to(REPO)}: {p.exists()}")
if a.exists() and b.exists():
    ta, tb = a.read_text(encoding="utf-8", errors="replace"), b.read_text(encoding="utf-8", errors="replace")
    a_imports_b = bool(re.search(r"^\s*(from\s+\S*write_path|import\s+\S*write_path|from\s+\.\s*import\s+[^\n]*write_path)", ta, re.M))
    b_imports_a = bool(re.search(r"^\s*(from\s+\S*sentinel|import\s+\S*sentinel|from\s+\.\s*import\s+[^\n]*sentinel)", tb, re.M))
    print(f"   sentinel imports write_path: {a_imports_b}")
    print(f"   write_path imports sentinel: {b_imports_a}")
    print(f"   CYCLE PRESENT: {a_imports_b and b_imports_a}")
    for nm, t in (("sentinel", ta), ("write_path", tb)):
        print(f"   -- {nm} import lines:",
              [ln.strip() for ln in t.split("\n") if ln.strip().startswith(("import ", "from "))][:8])
    # control: a pair that must NOT show a cycle
    c = REPO / "tools/crcp/crcp/__init__.py"
    if c.exists():
        tc = c.read_text(encoding="utf-8", errors="replace")
        print(f"   CONTROL __init__ imports sentinel AND sentinel imports __init__? "
              f"{bool(re.search('sentinel', tc)) and bool(re.search(r'from\\s+\\.\\s+import', ta))}")

# --- claim B (AUD-0051 review): "exactly ONE .coverage-thresholds.json, at tools/editor/metaswarm"
print("\nclaim B -- exactly one .coverage-thresholds.json in the repo?")
idx = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, encoding="utf-8").stdout.split("\n")
gi = [f for f in idx if f.endswith(".coverage-thresholds.json")]
disk = [str(p.relative_to(REPO)).replace("\\", "/") for p in REPO.rglob(".coverage-thresholds.json")]
print(f"   git index: {gi}")
print(f"   disk walk: {disk}")
print(f"   agree: {sorted(gi) == sorted(disk)}  count={len(gi)}")
print(f"   CONTROL finder locates a known-present file: "
      f"{bool([f for f in idx if f.endswith('WORK-UNIT-CATALOG.json')])}")
