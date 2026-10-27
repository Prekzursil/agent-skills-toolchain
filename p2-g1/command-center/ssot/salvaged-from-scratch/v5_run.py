"""V5: run the lane's own instruments with MY hash guard; verify no-write, counts, and that the
four ' M' REVIEW files are byte-identical to HEAD. Includes a control proving the hasher sees a
one-byte change."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
LANE = REPO / "command-center/p2-next"

ART = [
    "VENDOR-SATISFIABILITY.json", "REVIEW-GATE-SPLIT.json", "FINAL-VERIFY.json",
    "R2-CONTROL-STABILITY.json", "R2-RECONCILE.json", "R2-TAG-CENSUS.json",
    "P2NEXT-BUILD.md", "P2NEXT-BUILD-R2.md",
]


def snap():
    return {a: hashlib.sha256((LANE / a).read_bytes()).hexdigest()[:16] for a in ART if (LANE / a).exists()}


# --- control: does the hasher see a one-byte change?
probe = LANE / "__advver_tmp_probe.txt"
probe.write_bytes(b"a")
h1 = hashlib.sha256(probe.read_bytes()).hexdigest()
probe.write_bytes(b"b")
h2 = hashlib.sha256(probe.read_bytes()).hexdigest()
probe.unlink()
print(f"CONTROL hasher_sees_one_byte_change={h1 != h2} (must be True)")

SCRIPTS = [
    "vendor_satisfiability.py", "split_review_gate.py", "_b20_final_verify.py", "_r2_dod.py",
]
before = snap()
for s in SCRIPTS:
    p = LANE / s
    if not p.exists():
        print(f"MISSING {s}")
        continue
    r = subprocess.run([sys.executable, str(p)], cwd=REPO, capture_output=True,
                       encoding="utf-8", errors="replace")
    after = snap()
    changed = [k for k in before if before.get(k) != after.get(k)]
    print(f"\n##### {s}  rc={r.returncode}  artifacts_changed={changed}")
    out = (r.stdout or "") + (r.stderr or "")
    keep = [ln for ln in out.split("\n") if any(
        t in ln for t in ("BASIS", "VERDICT", "STABILITY", "RE-DERIVED", "buckets", "DoD",
                          "selftest", "drift", "problems", "SUCCESS", "FAILED", "only in",
                          "CROSS_VENDOR", "deciding rule", "Traceback", "Error"))]
    print("\n".join(keep[:30]))
    before = after

print("\n########## four ' M' REVIEW files: worktree bytes vs HEAD blob ##########")
for f in ["REVIEW-AUD-0006.json", "REVIEW-PREDICATE-PROBE.json", "REVIEW-THREE-RESOLVED.json",
          "REVIEW-TST0350-NC2.json"]:
    rel = f"command-center/p2-next/{f}"
    wt = (LANE / f).read_bytes()
    head = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=REPO, capture_output=True).stdout
    print(f"  {f:32s} wt={len(wt):7d} head={len(head):7d} identical={wt == head}")
# control: a genuinely divergent file
rel = "command-center/adversarial/ADV-0041-path-and-identity-disclosure.json"
wt = (REPO / rel).read_bytes()
head = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=REPO, capture_output=True).stdout
print(f"  CONTROL ADV-0041 wt={len(wt)} head={len(head)} identical={wt == head} (must be False)")
