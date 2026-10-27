"""ADV-VER both-states: feed REAL historical blobs through the SHIPPED gate function.

Pinned to immutable blob SHAs, never a rev. Fails closed on a missing/empty blob.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
GATE = ROOT / "ci" / "tests" / "test_docs_executable_claims.py"

spec = importlib.util.spec_from_file_location("gate", GATE)
gate = importlib.util.module_from_spec(spec)
sys.modules["gate"] = gate
spec.loader.exec_module(gate)

div = gate.measured_skill_root_divergence()
print(f"measured divergence: {div}")

# PRECONDITION: if the roots stopped diverging, the "broken" states would silently
# cease to be broken and this control would prove nothing. Abort loudly instead.
assert div["only_projection"] or div["only_canonical"], (
    "ABORT: roots no longer diverge; the broken states are no longer broken."
)


def blob(sha):
    p = subprocess.run(["git", "cat-file", "-p", sha], cwd=ROOT,
                       capture_output=True, check=True)
    raw = p.stdout
    assert raw, f"ABORT: blob {sha} is empty -- fail closed"
    return raw.decode("utf-8"), raw.count(b"\r")


states = {
    "BROKEN r1_overclaim (84bf3a33^)": "75b1e418",
    "BROKEN pre_r1": "d3c5b035",
    "FIXED shipped blob (84bf3a33)": "24022f1c",
}
results = {}
for label, sha in states.items():
    text, cr = blob(sha)
    v = gate.roadmap_violations(text, div)
    results[label] = len(v)
    print(f"--- {label} (blob {sha}, CR={cr}) -> {len(v)} violation(s)")
    for x in v:
        print(f"      {x}")

# FIXED must also be checked against the CURRENT worktree bytes (CRLF path).
wt = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
wt_cr = (ROOT / "docs" / "roadmap.md").read_bytes().count(b"\r")
v = gate.roadmap_violations(wt, div)
results[f"FIXED worktree (CR={wt_cr})"] = len(v)
print(f"--- FIXED worktree (CR={wt_cr}) -> {len(v)} violation(s)")

broken = [k for k in results if k.startswith("BROKEN")]
fixed = [k for k in results if k.startswith("FIXED")]
ok = all(results[k] >= 1 for k in broken) and all(results[k] == 0 for k in fixed)
print("SUCCESS:advver-bothstates " if ok else "FAILED:advver-bothstates ",
      {k: v for k, v in results.items()})
sys.exit(0 if ok else 1)
