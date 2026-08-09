"""Both-states control for the wfa-1 self-audit.

A probe that passes on the good state proves nothing unless it also FIRES on a
known-broken one. This corrupts ONE number in a TEMP COPY of the sidecar (the
real artifact is never modified) and requires the checker to exit non-zero.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REAL = Path("platform/registry/workflow-candidates-1.COVERAGE.json")
CHECK = "command-center/_wfa1_final_check.py"


def run(sidecar):
    r = subprocess.run(
        [sys.executable, CHECK, str(sidecar)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    tail = [ln for ln in (r.stdout or "").splitlines() if ln.startswith(("SUCCESS", "FAILED"))]
    return r.returncode, (tail[-1] if tail else "(no terminal marker)")


tmp = Path(tempfile.mkdtemp(prefix="wfa1_bothstates_"))
good = tmp / "good.json"
bad = tmp / "bad.json"
shutil.copy2(REAL, good)

txt = REAL.read_text(encoding="utf-8")
# single mutation: change the measured file count 328 -> 999 in the tree claim
mutated, n = re.subn(r"18 trees / 328 files", "18 trees / 999 files", txt, count=1)
assert n == 1, "mutation did not apply -- the control itself is broken"
bad.write_text(mutated, encoding="utf-8")

rc_good, msg_good = run(good)
rc_bad, msg_bad = run(bad)

print(f"[FIXED  state] rc={rc_good}  {msg_good}")
print(f"[BROKEN state] rc={rc_bad}  {msg_bad}")
print(f"real artifact untouched: {REAL.read_text(encoding='utf-8') == txt}")

ok = rc_good == 0 and rc_bad != 0
print()
print(
    "SUCCESS:wfa1-bothstates the self-audit passes on the real artifact AND fires on a "
    "single-number mutation -- it is measuring something"
    if ok
    else "FAILED:wfa1-bothstates the checker does not discriminate the two states"
)
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(0 if ok else 1)
