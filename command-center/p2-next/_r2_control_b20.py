"""ROUND-2 both-states control on the REPAIRED final verifier.

_b20_final_verify.py exits 0 today. Silence is only evidence if the same instrument goes RED on a
known-wrong state. So: copy it to a temp file with the expected committed count mutated 42 -> 41
(the round-1 number, now known to be the worktree figure) and confirm it exits NON-ZERO and names
the moved count. Then confirm the unmutated original still exits 0 in the same shell.

This is the control the round-1 verifier could not have: it read the count out of the producer's
artifact, so mutating the expectation and mutating the artifact were the same lever.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "command-center/p2-next/_b20_final_verify.py"

src = SRC.read_text(encoding="utf-8")
assert "EXPECTED_RAIL_COMMITTED = 42" in src, (
    "anchor missing -- control cannot be trusted"
)
mutated = src.replace("EXPECTED_RAIL_COMMITTED = 42", "EXPECTED_RAIL_COMMITTED = 41", 1)
assert mutated != src

with tempfile.TemporaryDirectory() as td:
    # keep it inside the lane dir so parents[2] still resolves to the repo root
    tmp = REPO / "command-center/p2-next/_r2_tmp_b20_mutant.py"
    tmp.write_text(mutated, encoding="utf-8", newline="\n")
    try:
        r = subprocess.run(
            [sys.executable, str(tmp)],
            cwd=REPO,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    finally:
        tmp.unlink(missing_ok=True)

tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-2:]
print(f"MUTANT (expect 41) rc={r.returncode}")
for ln in tail:
    print(f"   {ln}")

r2 = subprocess.run(
    [sys.executable, str(SRC)],
    cwd=REPO,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
tail2 = [ln for ln in (r2.stdout or "").splitlines() if ln.strip()][-1:]
print(f"ORIGINAL           rc={r2.returncode}")
for ln in tail2:
    print(f"   {ln}")

fires = r.returncode != 0 and "rail-blocked count moved to 42" in (r.stdout or "")
silent = r2.returncode == 0
print(f"\nCONTROL fires_on_wrong_expectation={fires} silent_on_correct={silent}")
print("SUCCESS:r2-control-b20" if (fires and silent) else "FAILED:r2-control-b20")
raise SystemExit(0 if (fires and silent) else 1)
