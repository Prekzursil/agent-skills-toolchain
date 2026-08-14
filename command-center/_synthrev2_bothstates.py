"""Both-states control: does check_published_commands.py actually SEE the fenced
`python command-center/_synthrev2_*.py` receipts in GRIND-STATUS.md?

A green gate proves nothing unless the gate fires on the known-broken state. Breaks ONE
published path to a nonexistent script, re-runs the gate, then restores byte-for-byte and
proves the restore with a sha256 comparison.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "command-center" / "GRIND-STATUS.md"
GATE = ["python", "command-center/slop-report/check_published_commands.py"]
GOOD = "python command-center/_synthrev2_gates.py"
BAD = "python command-center/_synthrev2_NOSUCHFILE.py"


def gate():
    p = subprocess.run(
        GATE, cwd=str(REPO), capture_output=True, text=True, errors="replace"
    )
    tail = (p.stdout + p.stderr).replace("\r\n", "\n").strip().split("\n")[-1]
    return p.returncode, tail


original = DOC.read_bytes()
before_sha = hashlib.sha256(original).hexdigest()

rc_clean, tail_clean = gate()

txt = DOC.read_text(encoding="utf-8", newline="")
if GOOD not in txt:
    sys.exit(f"FAILED:bothstates the probe anchor {GOOD!r} is not in the document")
DOC.write_text(txt.replace(GOOD, BAD, 1), encoding="utf-8", newline="")
try:
    rc_broken, tail_broken = gate()
finally:
    DOC.write_bytes(original)

after_sha = hashlib.sha256(DOC.read_bytes()).hexdigest()
restored = before_sha == after_sha

print(f"  clean  state: rc={rc_clean}  {tail_clean[:110]}")
print(f"  BROKEN state: rc={rc_broken}  {tail_broken[:110]}")
print(f"  restored byte-identical: {restored} ({before_sha[:12]})")

sees = rc_broken != 0
print(
    "SUCCESS:bothstates the gate SEES the fenced receipts (fired on the broken state)"
    if sees and restored and rc_clean == 0
    else f"FAILED:bothstates gate_sees={sees} restored={restored} rc_clean={rc_clean}"
)
sys.exit(0 if (sees and restored and rc_clean == 0) else 1)
