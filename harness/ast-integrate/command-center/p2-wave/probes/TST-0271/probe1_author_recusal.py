#!/usr/bin/env python3
"""Probe 1: author-reviews-own-artifact — declared conflict, ballot excluded.

A warning with the ballot still inside the tally is a failure. This probe
also runs the warning-only mutant and requires the exclusion assert to fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenario as F  # noqa: E402

C = F.C
S = F.S


def fail(msg: str) -> int:
    print(f"FAILED:TST-0271-probe1 {msg}")
    return 1


def main() -> int:
    spec = F.spec_declared()
    twice = S.run_twice(spec)
    live = twice["first"]["tally"]
    transcript = twice["first"]["transcript"]

    if live["counts"] != F.expected_honest_counts():
        return fail(f"tally {live['counts']} want {F.expected_honest_counts()}")
    if live["n_submitted"] != 3 or live["n_counting"] != 2 or live["n_excluded"] != 1:
        return fail(
            f"n_submitted={live['n_submitted']} n_counting={live['n_counting']} "
            f"n_excluded={live['n_excluded']}"
        )
    if F.AUTHOR in live["counting_seat_ids"]:
        return fail("conflicted author still in counting_seat_ids")
    if F.AUTHOR not in live["excluded_seat_ids"]:
        return fail("author ballot not in excluded_seat_ids")
    if F.INDEP_A not in live["counting_seat_ids"] or F.INDEP_B not in live["counting_seat_ids"]:
        return fail("unconflicted seats missing from counting set")

    row = live["excluded"][0]
    audit = row.get("audit") or ""
    if "CONFLICT" not in audit or F.AUTHOR not in audit:
        return fail(f"audit line does not name the seat: {audit}")
    if "authored_the_artifact" not in audit:
        return fail(f"audit line does not name the kind: {audit}")
    if "declared" not in row.get("sources") and "declared" not in audit:
        return fail(f"declared source missing: {row.get('sources')} {audit}")
    if row.get("counting") is True or int(row.get("weight") or 0) != 0:
        return fail("excluded row still has counting weight")

    naive = C.naive_count_all(F.ballots())
    if naive != F.expected_naive_counts():
        return fail(f"naive hand-count drifted {naive}")
    if live["counts"] == naive:
        return fail("production tally equals naive all-ballots count; recusal is a no-op")

    mutant = C.warning_only_mutant(F.seats_declared(), F.artifact(), F.ballots())
    if mutant["counts"] != naive:
        return fail("mutant did not keep the conflicted ballot in counts")
    if "warning" not in mutant:
        return fail("mutant missing warning text")
    caught = False
    try:
        C.assert_no_conflicted_counting_vote(mutant)
    except C.ConflictError:
        caught = True
    if not caught:
        return fail("warning-only mutant was accepted; declared-but-counted must fail")

    C.assert_no_conflicted_counting_vote(live)

    out = {
        "pass": True,
        "probe": "probe1-author-recusal",
        "unit_id": "TST-0271",
        "tally": live["counts"],
        "n_counting": live["n_counting"],
        "n_excluded": live["n_excluded"],
        "excluded_seat_ids": live["excluded_seat_ids"],
        "counting_seat_ids": live["counting_seat_ids"],
        "audit_line": audit,
        "naive_counts_if_counted": naive,
        "warning_only_mutant_caught": True,
        "transcript_sha256": twice["transcript_sha256"],
        "simulator": transcript["simulator"],
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0271-probe1 author ballot excluded from tally")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
