#!/usr/bin/env python3
"""Probe 2: independent recount / re-tabulation. A number disagreement blocks."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import reviewer as R  # noqa: E402
from runtime import duplicate_pairs, run  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0021-participant-replacement-and-duplicate-independence-detecti.md"
)
SENTINEL = "SUCCESS:CNL-0021"


def _fail(msg: str) -> int:
    print(f"FAILED:CNL-0021-probe2 {msg}")
    return 1


def main() -> int:
    c, script = F.midround_death_honest()
    run(c, script)
    death = R.recount_death(c, "seat-architect", "seat-architect-r2")
    print("recount_death=" + json.dumps(death, sort_keys=True))

    if death["status"] != "REPLACED-AND-CONTINUED":
        return _fail(f"status {death['status']}")
    if death["hung"]:
        return _fail("hung")
    if death["inherited"] != 0:
        return _fail(f"inherited {death['inherited']}")
    if death["dead_ballots"] < 1:
        return _fail("dead seat has no historical ballots")
    if death["replacement_ballots"] < 1:
        return _fail("replacement cast nothing after seating")
    if death["idea_origins"].get("I1") != "seat-architect":
        return _fail(f"idea origin {death['idea_origins']}")

    c_mut, s_mut = F.midround_death_inherit_mutant()
    run(c_mut, s_mut)
    mut = R.recount_death(c_mut, "seat-architect", "seat-architect-r2")
    if mut["inherited"] < 1:
        return _fail("inheritance mutant recount silent")
    print(f"inheritance_mutant_inherited={mut['inherited']}")

    same = F.roster_same_base_model_different_roles()
    pairs_same = R.pairwise_duplicate_seat_ids(same)
    grouped_same = [
        tuple(sorted(f.seats))
        for f in duplicate_pairs(same)
        if f.code == "DUPLICATE-INDEPENDENCE"
    ]
    # Author groups whole cliques; pairwise emits edges. For 2 seats they match.
    if pairs_same != [("s-arch", "s-skep")]:
        return _fail(f"pairwise same {pairs_same}")
    if grouped_same != [("s-arch", "s-skep")]:
        return _fail(f"grouped/pairwise disagree {grouped_same} vs {pairs_same}")
    print(f"pairwise_same={pairs_same}")

    diff = F.roster_genuinely_different()
    pairs_diff = R.pairwise_duplicate_seat_ids(diff)
    if pairs_diff:
        return _fail(f"pairwise different flagged {pairs_diff}")
    print("pairwise_different=[]")

    xv = F.roster_cross_vendor_same_model()
    pairs_xv = R.pairwise_duplicate_seat_ids(xv)
    if pairs_xv != [("s-az", "s-oa")]:
        return _fail(f"pairwise cross-vendor {pairs_xv}")

    gpt = F.roster_gpt4o_vs_gpt41()
    if R.pairwise_duplicate_seat_ids(gpt):
        return _fail("gpt-4o vs gpt-4.1 pairwise flagged")

    una = F.roster_unattested()
    if R.unattested_seat_ids(una) != ["s-ghost"]:
        return _fail(f"unattested {R.unattested_seat_ids(una)}")
    if R.pairwise_duplicate_seat_ids(una):
        return _fail("unattested treated as duplicate pair")

    tri = F.roster_three_with_one_duplicate()
    if R.pairwise_duplicate_seat_ids(tri) != [("s-arch", "s-skep")]:
        return _fail(f"three-seat pairwise {R.pairwise_duplicate_seat_ids(tri)}")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            return _fail(f"artifact-unparseable {exc}")
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"self-declared {doc.get('state')}")
        if SENTINEL not in text:
            return _fail("sentinel-absent")
        measured = doc.get("measured") or {}
        want = {
            "honest_status": death["status"],
            "honest_inherited": death["inherited"],
            "honest_dead_ballots": death["dead_ballots"],
            "honest_replacement_ballots": death["replacement_ballots"],
            "same_base_pair_count": len(pairs_same),
            "different_pair_count": len(pairs_diff),
            "inherit_mutant_inherited": mut["inherited"],
        }
        for key, val in want.items():
            got = measured.get(key)
            if got != val:
                return _fail(f"recount disagree {key} artifact={got} recount={val}")
        rev = doc.get("reviewer") or {}
        if rev.get("recount_agrees") is not True:
            return _fail("artifact reviewer.recount_agrees is not true")
        print("artifact_recount_agrees=true")
    else:
        print("artifact_absent_at_probe2_run")

    print("SUCCESS:CNL-0021-probe2 independent pairwise recount agrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
