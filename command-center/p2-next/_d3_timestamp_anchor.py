"""Both-states proof that claim_gate stopped accepting a TIMESTAMP as an evidence anchor.

A gate that reads a claim is not a gate, so this does not inspect the regex -- it runs the real
CLI, twice, with ONE unmodified probe:

  OLD  = claim_gate.py at PRE_FIX, the commit before the fix landed
  NEW  = claim_gate.py in the worktree

OLD is PINNED to a SHA, not to `HEAD`. It read `HEAD` while the fix was still uncommitted, which
was correct exactly once: the moment the fix was committed, `HEAD` began carrying the FIX, case C
became "old exit 1, new exit 1", and this probe reported FAILED for a defect that was closed. A
committed probe that goes red when re-run is a landmine for the next reader, so the before-state
is now named explicitly and this file stays truthful on every future run.

Three cases, and the middle one is the load-bearing control:

  A  a well-formed CONFIRMED claim with a real file:line anchor
       must exit 0 in BOTH states -- otherwise the fix is a false-positive machine.
  B  a CONFIRMED claim with obvious non-evidence ("I recall seeing it")
       must exit 1 in BOTH states -- proves the anchor rule was ALREADY LIVE in the old
       state, so a silence in case C is a real hole and not a dead instrument.
  C  a CONFIRMED claim whose only evidence is `2026-08-12T05:15:00`
       old exit 0 -> new exit 1 is the defect and its closure.

Without B, case C flipping would be indistinguishable from "the old gate did nothing at all".
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE = ".agents/skills/claim-verify-gate/scripts/claim_gate.py"
# The parent of 1b1e1e4e ("a timestamp was a valid evidence anchor"), i.e. the last commit whose
# claim_gate.py still carried `_ANCHOR = re.compile(r"https?://\S+|\S+:\d+")`. Override with
# argv[1] to re-point the before-state at another rev.
PRE_FIX = "5d573583"

PROBE = {
    "tool": "python",
    "engine": "cpython",
    "shell": "powershell",
    "field": "exit_code",
}
VERIFY = {"tool": "git", "engine": "git", "shell": "bash", "field": "blob_bytes"}


def ledger(evidence: list[str]) -> dict:
    return {
        "subject": "timestamp-anchor probe",
        "claims": [
            {
                "id": "C1",
                "text": "The gate rejects a timestamp as an evidence anchor.",
                "verdict": "CONFIRMED",
                "band": "almost certain",
                "scope": "the three cases in this probe",
                "source_probe": dict(PROBE),
                "verify_probe": dict(VERIFY),
                "evidence": evidence,
            }
        ],
    }


CASES = [
    (
        "A real file:line anchor",
        ["command-center/p2-next/rail_count_gate.py:133"],
        0,
        0,
    ),
    ("B obvious non-evidence (control)", ["I recall seeing it"], 1, 1),
    ("C bare timestamp (the defect)", ["2026-08-12T05:15:00"], 0, 1),
]


def run(gate_path: Path, payload: dict, work: Path) -> int:
    claims = work / "ledger.json"
    claims.write_text(json.dumps(payload), encoding="utf-8", newline="")
    proc = subprocess.run(
        [sys.executable, str(gate_path), "--claims", str(claims), "--format", "json"],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    rev = (argv if argv is not None else sys.argv[1:] or [PRE_FIX])[0]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        old = work / "claim_gate_old.py"
        blob = subprocess.run(
            ["git", "show", f"{rev}:{GATE}"],
            cwd=REPO,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if blob.returncode != 0:
            print(f"FAILED: cannot read claim_gate.py at {rev}")
            return 2
        old.write_text(blob.stdout, encoding="utf-8", newline="")
        new = REPO / GATE
        # Fail closed: if the before-state does NOT carry the old rule, this probe is comparing
        # two fixed gates and its silence would mean nothing.
        if "_is_anchor" in blob.stdout:
            print(f"FAILED: {rev} already carries the fix; it is not a before-state")
            return 2

        print(f"OLD = {rev}:{GATE}")
        print(f"NEW = worktree {GATE}")
        print()
        bad = 0
        for label, evidence, want_old, want_new in CASES:
            got_old = run(old, ledger(evidence), work)
            got_new = run(new, ledger(evidence), work)
            ok = (got_old, got_new) == (want_old, want_new)
            bad += not ok
            print(
                f"  {'ok  ' if ok else 'FAIL'}  {label}: "
                f"old exit {got_old} (want {want_old}), new exit {got_new} (want {want_new})"
            )
        print()
        if bad:
            print(f"FAILED:timestamp-anchor {bad} case(s) did not match")
            return 1
        print("SUCCESS:timestamp-anchor old accepted the timestamp, new rejects it,")
        print("        and the control proves the rule was live in both states.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
