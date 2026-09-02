#!/usr/bin/env python3
"""Probe 1: recusal lifecycle, quorum recomputation, retained census."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402
from tools.council.integrity.recusal import RecusalError  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0361.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0361-probe1 {msg}")
    return 1


def main() -> int:
    life = S.declare_recuse_replace()
    voided = S.quorum_void_then_restore()
    print(json.dumps({"lifecycle": life, "quorum_void": voided}, sort_keys=True))

    if not life["recusal_declared"]:
        return fail("recusal proceeded without a recorded declaration")
    if life["recused_still_counts"]:
        return fail("recused seat still in recomputed counting set")
    if life["recused_in_recomputed"]:
        return fail("compare_tallies recused_in_recomputed")
    if not life["recused_in_recorded"]:
        return fail("recorded tally dropped the recused ballot (nothing to exclude)")
    if not life["differ"]:
        return fail("recorded and recomputed tallies are identical")
    if life["pre_decision"] != "approve":
        return fail(f"pre-recusal decision {life['pre_decision']!r} != approve")
    if life["recorded_decision"] != "approve":
        return fail("recorded tally no longer elects approve")
    if life["recomputed_decision"] is not None:
        return fail(
            f"recomputed decision {life['recomputed_decision']!r} "
            "must not elect after the recused approve is excluded (2-2)"
        )
    if life["recomputed_counts"].get("approve") != 2:
        return fail(f"recomputed approve {life['recomputed_counts']}")
    if life["recomputed_counts"].get("reject") != 2:
        return fail(f"recomputed reject {life['recomputed_counts']}")
    if life["recorded_counts"].get("approve") != 3:
        return fail(f"recorded approve {life['recorded_counts']}")
    if not life["census_retained"]:
        return fail(f"census dropped pre-recusal contributions {life['census']}")
    if "idea-A1" not in life["retained_contribution_ids"]:
        return fail("idea-A1 missing from recusal retained list")
    if life["contribution_hashes_pre"].get("idea-A1") != life[
        "contribution_hashes_post"
    ].get("idea-A1"):
        return fail("idea-A1 hash drifted across recusal")
    if life["honest_audit"]["fired"]:
        return fail("honest counting set fired the recused-ballot detector")
    if not life["recorded_audit"]["fired"]:
        return fail("recorded tally (recused ballot left in) did not fire")
    if life["inherited_ballots"] != 0 or life["replace_inherited_ballots"] != 0:
        return fail("replacement inherited ballots")
    if life["post_quorum"]["eligible_n"] != 4:
        return fail(f"post-recusal eligible {life['post_quorum']}")
    if not life["post_quorum"]["met"]:
        return fail("quorum should still hold after one recusal of five")
    if life["after_replace_quorum"]["eligible_n"] != 5:
        return fail(f"replace did not restore eligible {life['after_replace_quorum']}")

    if not voided["void"] or voided["void_eligible_n"] != 2:
        return fail(f"expected void at eligible=2, got {voided}")
    if voided["void_reason"] != "quorum":
        return fail(f"void reason {voided['void_reason']!r}")
    if voided["void_decision"] is not None:
        return fail("void panel still produced a decision")
    if not voided["restored_met"] or voided["restored_eligible_n"] != 3:
        return fail(f"replacement did not restore quorum {voided}")

    session = S.seated_and_voted()
    session.declare(
        S.RECUSED,
        S.Conflict(kind="authored_artifact", target=S.ARTIFACT),
    )
    session.recuse(S.RECUSED, reason="authored the artifact under review")
    try:
        session.cast_ballot(
            S.Ballot(
                ballot_id="b-seat-A-late",
                seat_id=S.RECUSED,
                choice="approve",
                round_id=2,
            )
        )
        return fail("recused seat cast a later ballot")
    except RecusalError:
        pass

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0361" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    measured = doc.get("measured") or {}
    if measured.get("recomputed_approve") != 2:
        return fail("receipt recomputed_approve drift")
    if measured.get("recorded_approve") != 3:
        return fail("receipt recorded_approve drift")
    if measured.get("recused_still_counts") is not False:
        return fail("receipt did not record recused_still_counts=false")
    if measured.get("census_retained") is not True:
        return fail("receipt census_retained drift")

    print(
        "recused_counts=False recomputed=2-2 recorded=3-2 "
        f"census_retained={life['census_retained']} "
        f"void_then_restore={voided['restored_met']}"
    )
    print("SUCCESS:IMP-0361-probe1 lifecycle and quorum recomputation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
