"""Is the documented claim_gate hole still live, and is claim_gate reusable for the C5 floor?

rules/common/single-signal-verification.md asserts: a CONFIRMED claim with NO source_probe,
one verifier, and a syntactically valid evidence anchor returns violations=[], ok=true, exit 0 --
so the gate certifies corroboration for a claim that declares no producing measurement.

That is a CLAIM about our own tool. Execute it, in both states.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE = REPO / ".agents/skills/claim-verify-gate/scripts/claim_gate.py"


def run(payload: dict, label: str) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump(payload, fh)
        p = fh.name
    # NOTE: the payload path is passed via --claims. A bare positional argument exits 2
    # ("unusable input"), which is NOT a verdict -- the first run of this probe made that
    # mistake and controls A and B caught it before any conclusion was drawn.
    r = subprocess.run(
        [sys.executable, str(GATE), "--claims", p, "--format", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    Path(p).unlink(missing_ok=True)
    print(f"\n[{label}] exit={r.returncode}")
    print("   " + (r.stdout or r.stderr).strip().replace("\n", "\n   ")[:600])
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def claim(**over) -> dict:
    base = {
        "id": "G4-1",
        "text": "the split is 42 rail-blocked of 52",
        "verdict": "CONFIRMED",
        "evidence": ["command-center/p2-next/vendor_satisfiability.py:342"],
        "verify_probe": {
            "tool": "python",
            "target": "split_review_gate.py",
            "field": "verdict",
        },
        "source_probe": {
            "tool": "python",
            "target": "vendor_satisfiability.py",
            "field": "rule",
        },
    }
    base.update(over)
    return base


def main() -> int:
    # State A -- control: a well-formed claim WITH a source_probe must pass.
    a, _ = run({"claims": [claim()]}, "A control: full claim, distinct probes")

    # State B -- control: identical probes must be CAUGHT (proves the gate is not inert).
    same = {"tool": "python", "target": "x.py", "field": "f"}
    b, b_out = run(
        {"claims": [claim(source_probe=dict(same), verify_probe=dict(same))]},
        "B control: source_probe == verify_probe (must FAIL)",
    )

    # State C -- the documented hole: CONFIRMED with NO source_probe at all.
    c_payload = claim()
    c_payload.pop("source_probe")
    c, c_out = run({"claims": [c_payload]}, "C hole: CONFIRMED with NO source_probe")

    print("\n" + "=" * 78)
    ok_a, ok_b = a == 0, b == 1
    hole = c == 0
    print(f"A full claim passes                 : {ok_a} (exit {a})")
    print(
        f"B same-probe rerun is CAUGHT        : {ok_b} (exit {b})  <- detector is live"
    )
    print(f"C missing source_probe still passes : {hole} (exit {c})")

    if not ok_a or not ok_b:
        print("\nFAILED:g4 controls misbehaved -- verdict untrustworthy")
        return 1
    if hole:
        print(
            "\nCONFIRMED: the hole is LIVE. claim_gate certifies a CONFIRMED verdict that declares\n"
            "no producing measurement. Reusing it as the C5 content floor REQUIRES closing this\n"
            "first, or the floor inherits the same defect.\n"
            "SUCCESS:g4-claimgate-hole CONFIRMED"
        )
    else:
        print(
            "\nREFUTED: the hole is already closed; claim_gate is reusable as-is.\nSUCCESS:g4-claimgate-hole REFUTED"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
