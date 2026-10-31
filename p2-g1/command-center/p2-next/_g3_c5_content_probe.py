"""Does C5 actually verify the CONTENT of a review, or only its verdict flags?

CROSS-VENDOR-RAIL-STATUS.md residual #4 asserts a gap: "A reviewer PASS with empty reasoning
would satisfy C5." That is a CLAIM. This probe EXECUTES it.

Method: import the real gate, monkeypatch only the blob reader so check_reviewed() sees a
mutated receipt set, and observe the verdict. No receipt on disk or in git is touched.

Both states are run, because a probe that is silent in both measures nothing:
  state A (control)  : unmutated receipts        -> C5 must report 10 reviewed, 0 problems
  state B (mutation) : reviewer.notes emptied    -> if C5 still passes, the gap is CONFIRMED
  state C (control2) : reviewer.verdict=FAIL     -> C5 MUST fail, proving the probe can see failure
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "command-center" / "p2-next"))

spec = importlib.util.spec_from_file_location(
    "rail_count_gate", REPO / "command-center/p2-next/rail_count_gate.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

NOTE_KEYS = ("notes", "reasoning", "falsification_method", "method", "summary")


def run(label: str, mutate) -> tuple[int, int]:
    rows = gate.satisfiable_rows("committed")
    real = gate._vs.batch_blobs("HEAD", [r["output_path"] for r in rows])
    mutated = {}
    for path, txt in real.items():
        rec = json.loads(txt)
        mutate(rec)
        mutated[path] = json.dumps(rec)

    orig = gate._vs.batch_blobs
    gate._vs.batch_blobs = lambda rev, paths: {
        p: mutated[p] for p in paths if p in mutated
    }
    try:
        # check_reviewed grew a third return value this round (an ADVISORY count of receipts
        # carrying a resolving evidence anchor). Only the caller is adapted -- the A/B/C states
        # and every verdict below are exactly as this probe was written, so the flip from
        # CONFIRMED to REFUTED is the fix landing, not the probe being retuned.
        reviewed, problems, _anchored = gate.check_reviewed("committed", rows)
    finally:
        gate._vs.batch_blobs = orig

    print(f"\n[{label}]")
    print(f"   rows={len(rows)}  reviewed={reviewed}  problems={len(problems)}")
    for p in problems[:3]:
        print(f"     {p[:150]}")
    return reviewed, len(problems)


def strip_notes(rec: dict) -> None:
    rv = rec.get("reviewer")
    if isinstance(rv, dict):
        for k in NOTE_KEYS:
            if k in rv:
                rv[k] = ""


def fail_verdict(rec: dict) -> None:
    rv = rec.get("reviewer")
    if isinstance(rv, dict):
        rv["verdict"] = "FAIL"


def main() -> int:
    a_rev, a_prob = run("A control: receipts unmutated", lambda r: None)
    b_rev, b_prob = run("B mutation: every reviewer note emptied", strip_notes)
    c_rev, c_prob = run("C control2: reviewer verdict flipped to FAIL", fail_verdict)

    print("\n" + "=" * 78)
    ok_a = a_rev == 10 and a_prob == 0
    ok_c = c_prob > 0
    gap = b_rev == a_rev and b_prob == 0

    print(
        f"A unmutated passes                : {ok_a}   (reviewed={a_rev}, problems={a_prob})"
    )
    print(
        f"C flipped-verdict FAILS the gate  : {ok_c}   (problems={c_prob})  <- probe can see failure"
    )
    print(
        f"B empty-notes STILL passes        : {gap}   (reviewed={b_rev}, problems={b_prob})"
    )

    if not ok_a or not ok_c:
        print(
            "\nFAILED:g3-c5-content-probe controls did not behave -- verdict not trustworthy"
        )
        return 1
    if gap:
        print(
            "\nCONFIRMED: C5 is verdict-shaped only. Emptying EVERY reviewer note across all 10\n"
            "satisfiable units changes nothing -- the gate reports the same 10 reviewed, 0 problems.\n"
            "The residual documented in CROSS-VENDOR-RAIL-STATUS.md #4 is real and executable.\n"
            "SUCCESS:g3-c5-content-probe gap CONFIRMED"
        )
        return 0
    print(
        "\nREFUTED: C5 reacted to the note mutation -- the documented residual is wrong"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
