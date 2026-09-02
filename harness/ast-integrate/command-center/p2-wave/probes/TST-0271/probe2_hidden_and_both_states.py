#!/usr/bin/env python3
"""Probe 2: hidden COI via provenance join + both-states unconflicted count.

Starts from the fixtures, not the receipt narrative. Empty declaration must
still recuse when seat identity matches artifact.authors. An unconflicted
seat on the same artifact must count.
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
    print(f"FAILED:TST-0271-probe2 {msg}")
    return 1


def main() -> int:
    hidden = S.run(F.spec_undeclared())["tally"]
    declared = S.run(F.spec_declared())["tally"]

    if hidden["counts"] != F.expected_honest_counts():
        return fail(f"hidden tally {hidden['counts']}")
    if F.AUTHOR in hidden["counting_seat_ids"]:
        return fail("undeclared author still counted")
    if F.AUTHOR not in hidden["excluded_seat_ids"]:
        return fail("undeclared author not excluded")

    row = hidden["excluded"][0]
    if "provenance" not in row.get("sources", []):
        return fail(f"expected provenance source, got {row.get('sources')}")
    if "authored_the_artifact" not in row.get("kinds", []):
        return fail(f"expected authored_the_artifact, got {row.get('kinds')}")
    audit = row.get("audit") or ""
    if "CONFLICT" not in audit or "provenance" not in audit:
        return fail(f"audit line missing provenance join: {audit}")
    if F.AUTHOR not in audit:
        return fail(f"audit line does not name the seat: {audit}")

    # Both-states: same artifact, unconflicted seats must count (not an
    # over-broad recusal that empties the panel).
    for sid in (F.INDEP_A, F.INDEP_B):
        if sid not in hidden["counting_seat_ids"]:
            return fail(f"unconflicted {sid} recused on the same artifact")
    if hidden["n_counting"] != 2:
        return fail(f"both-states n_counting={hidden['n_counting']} want 2")

    # Declared and hidden paths must agree on the counting set.
    if hidden["counting_seat_ids"] != declared["counting_seat_ids"]:
        return fail("declared vs hidden counting sets diverged")
    if hidden["counts"] != declared["counts"]:
        return fail("declared vs hidden tallies diverged")

    # Over-broad control: a seat declaring a conflict on a different artifact
    # must still count here.
    seats = F.seats_undeclared()
    seats[1]["conflicts"] = [
        {"kind": "authored_the_artifact", "artifact_id": "art-not-this-one"}
    ]
    foreign = C.enforce(seats, F.artifact(), F.ballots())
    if F.INDEP_A not in foreign["counting_seat_ids"]:
        return fail("foreign-artifact declaration emptied the independent seat")

    # Require-the-field: omitting conflicts is not the same as declaring [].
    missing = F.seats_undeclared()
    del missing[0]["conflicts"]
    refused = False
    try:
        C.enforce(missing, F.artifact(), F.ballots())
    except C.ConflictError as exc:
        refused = "conflicts field missing" in str(exc)
    if not refused:
        return fail("seat without a conflicts field was accepted")

    C.assert_no_conflicted_counting_vote(hidden)

    out = {
        "pass": True,
        "probe": "probe2-hidden-and-both-states",
        "unit_id": "TST-0271",
        "hidden_tally": hidden["counts"],
        "hidden_excluded_seat_ids": hidden["excluded_seat_ids"],
        "hidden_counting_seat_ids": hidden["counting_seat_ids"],
        "provenance_source": "provenance" in row.get("sources", []),
        "audit_line": audit,
        "unconflicted_counted": True,
        "declared_hidden_tally_agree": True,
        "foreign_declaration_still_counts": True,
        "missing_field_refused": True,
        "both_states": {
            "conflicted_excluded": True,
            "unconflicted_counted": True,
        },
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0271-probe2 provenance join recuses; unconflicted counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
