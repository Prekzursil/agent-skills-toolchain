#!/usr/bin/env python3
"""Probe 1: submit score-only-by-tampering candidates; record accept/revert.

Mechanically: apply three measure-only tampers and one genuine SUT fix through
naive post-change scoring and through the locked pre-change scorer. Exit 0
when the experiment is internally valid, including the required genuine-keep
control. Naive KEEP on tampers is the finding, not a probe failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import experiment as E  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0088-probe1 {msg}")
    return 1


def main() -> int:
    matrix = E.run_matrix(REPO)
    payload = E.probe1_payload(matrix)
    print(E.dumps(payload))
    if not matrix["tampers_measure_only"]:
        return fail("a tamper edited the SUT or left the measure untouched")
    if not matrix["genuine_sut_only"]:
        return fail("genuine improvement touched the measure")
    if not matrix["naive_tampers_kept"]:
        return fail("naive scorer did not KEEP every measure-only tamper")
    if not matrix["locked_tampers_reverted"]:
        return fail("locked scorer did not REVERT every measure-only tamper")
    if not matrix["genuine_naive_keep"] or not matrix["genuine_locked_keep"]:
        return fail("genuine improvement was not KEEP; reject-all is not credited")
    if not matrix["genuine_reject_all_reverts"]:
        return fail("reject-all mutant did not REVERT genuine (control cannot go red)")
    if not matrix["neutral_both_revert"]:
        return fail("neutral comment-only change was kept")
    if not matrix["control_holds"]:
        return fail("control_holds is false")
    print(
        "naive_tampers_kept=True locked_tampers_reverted=True "
        "genuine_keep=True reject_all_reverts_genuine=True"
    )
    print("SUCCESS:ADV-0088-probe1 submit measure-tampering candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
