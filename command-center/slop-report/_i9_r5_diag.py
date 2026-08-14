"""Diagnose R5: WHICH lines of the source porcelain move while a clone-run is in flight.

R5 came back false. Two hypotheses, and they demand opposite responses:
  H1 the clone-run wrote into the SOURCE worktree -- the round-7 defect, a real finding.
  H2 a SIBLING lane mutated the shared tree during my run -- my control is an equality test
     against a moving value, which round 7 already recorded as "not an invariant".

A verdict of "R5 false" cannot distinguish them, so it is not yet evidence of anything.
This prints the actual delta and attributes it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = Path(
    subprocess.run(
        ["git", "-C", str(_HERE), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    ).stdout.strip()
)

# The only file the claims gate could ever write. If H1 were true this is what would move.
GATE_WRITES = ROOT / "command-center/slop-report/_r6_transcript.out.json"


def porcelain() -> list[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", "-uall"],
        capture_output=True,
        text=True,
    ).stdout.splitlines()


def sig(p: Path) -> dict:
    if not p.exists():
        return {"exists": False}
    st = p.stat()
    return {"exists": True, "size": st.st_size, "mtime_ns": st.st_mtime_ns}


def main() -> int:
    before, head_before = (
        porcelain(),
        subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip(),
    )
    gate_before = sig(GATE_WRITES)

    # Reproduce the same shape of work: a clone, held long enough for a sibling to act.
    t0 = time.time()
    subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
    )
    time.sleep(12)
    elapsed = round(time.time() - t0, 1)

    after, head_after = (
        porcelain(),
        subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip(),
    )
    gate_after = sig(GATE_WRITES)

    added = [ln for ln in after if ln not in before]
    removed = [ln for ln in before if ln not in after]
    mine = [
        ln
        for ln in added + removed
        if "slop-report" in ln and "_i9" not in ln and "SLOP-INTEGRATE-R2" not in ln
    ]
    res = {
        "elapsed_s": elapsed,
        "head_moved": head_before != head_after,
        "head_before": head_before[:8],
        "head_after": head_after[:8],
        "porcelain_lines_before": len(before),
        "porcelain_lines_after": len(after),
        "added": added,
        "removed": removed,
        # H1's signature: the file the gate writes changed.
        "H1_gate_output_moved": gate_before != gate_after,
        "gate_output_before": gate_before,
        "gate_output_after": gate_after,
        # H2's signature: churn outside anything this round touches.
        "H2_foreign_churn": [ln for ln in added + removed if "slop-report" not in ln],
        "lane_owned_churn_excluding_my_new_files": mine,
    }
    res["verdict"] = (
        "H1-CLONE-WROTE-INTO-SOURCE"
        if res["H1_gate_output_moved"]
        else ("H2-SIBLING-CHURN" if (added or removed) else "NO-MOVEMENT")
    )
    print(json.dumps(res, indent=1, sort_keys=True))
    out = ROOT / "command-center/slop-report/_i9_r5_diag.out.json"
    out.write_text(
        json.dumps(res, indent=1, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"wrote {os.path.basename(str(out))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
