"""Both-states proof, through the real CLI, that `host.tld:port` stopped passing as an anchor.

A gate that reads a claim is not a gate, and a predicate read in isolation is not the gate either
-- so this does not import `_is_anchor`. It writes a claim ledger to disk and runs claim_gate.py
as a subprocess, twice: once from the committed BEFORE blob, once from the worktree.

Four cases, and the second is the load-bearing control:

  A  a real file:line anchor                      0 -> 0   the fix must not be a false-positive machine
  B  obvious non-evidence ("I recall seeing it")   1 -> 1   CONTROL: proves the anchor rule was
                                                            ALREADY LIVE before, so a silence on C
                                                            is a real hole and not a dead instrument
  C  `example.com:443` (the audited defect)        0 -> 1   the hole and its closure
  D  `.gitattributes:2` (a real dotfile anchor)    1 -> 0   the OTHER direction: a pre-existing
                                                            false positive that the same change fixes

Without B, C flipping would be indistinguishable from "the old gate did nothing at all"; without
D, the change would look purely restrictive when it is measurably not.

BEFORE is pinned to a SHA. If it already carries the fix this exits 2 rather than reporting a
pass, so the probe stays truthful when re-run after the fix is committed.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE = ".agents/skills/claim-verify-gate/scripts/claim_gate.py"
BEFORE_REV = "5423de0f"

PROBE = {
    "tool": "python",
    "engine": "cpython",
    "shell": "powershell",
    "field": "exit_code",
}
VERIFY = {"tool": "git", "engine": "git", "shell": "bash", "field": "blob_bytes"}


def ledger(evidence: list[str]) -> dict:
    return {
        "subject": "host:port anchor probe",
        "claims": [
            {
                "id": "C1",
                "text": "The gate rejects a host:port as an evidence anchor.",
                "verdict": "CONFIRMED",
                "band": "almost certain",
                "scope": "the four cases in this probe",
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
    ("B obvious non-evidence (CONTROL)", ["I recall seeing it"], 1, 1),
    ("C host.tld:port (the defect)", ["example.com:443"], 0, 1),
    ("D .gitattributes:2 (false positive)", [".gitattributes:2"], 1, 0),
]


def run(gate: Path, payload: dict, work: Path) -> int:
    claims = work / "ledger.json"
    claims.write_text(json.dumps(payload), encoding="utf-8", newline="")
    proc = subprocess.run(
        [sys.executable, str(gate), "--claims", str(claims), "--format", "json"],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    rev = args[0] if args else BEFORE_REV
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
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
        if "_FILE_EXTENSIONS" in blob.stdout:
            print(f"FAILED: {rev} already carries the fix; it is not a before-state")
            return 2
        old = work / "claim_gate_old.py"
        old.write_text(blob.stdout, encoding="utf-8", newline="")
        new = REPO / GATE

        print(f"OLD = {rev}:{GATE}")
        print(f"NEW = worktree {GATE}\n")
        bad = 0
        for label, evidence, want_old, want_new in CASES:
            got_old = run(old, ledger(evidence), work)
            got_new = run(new, ledger(evidence), work)
            ok = got_old == want_old and got_new == want_new
            bad += 0 if ok else 1
            print(
                f"  {'ok  ' if ok else 'FAIL'}  {label:<36} "
                f"old exit {got_old} (want {want_old}), new exit {got_new} (want {want_new})"
            )
        if bad:
            print(
                f"\nFAILED:e4-hostport-anchor {bad} of {len(CASES)} cases did not match"
            )
            return 1
        print(
            "\nSUCCESS:e4-hostport-anchor 4/4 cases matched, control fires in BOTH states"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
