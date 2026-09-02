#!/usr/bin/env python3
"""Named probe 2: planted-drop and summarised-away both-states control.

The reviewer starts from these tests, not from the author's summary.
Good state (intact synthesis) must be silent. Bad state (one dissent
removed, or a claim replaced with a generic gloss) must fire.
A check green in both states measures nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.outcomes.dissent import (  # noqa: E402
    DissentPipeline,
    conservation,
    dissents_from_artifact,
    drop_dissent,
    presence_check,
    summarise_away,
)
from scenario import majority, two_dissent_council  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0312.json"
UNIT = "IMP-0312"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt artifact missing")
    if "SUCCESS:IMP-0312" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    pipe = DissentPipeline()
    good = pipe.run(two_dissent_council(), majority=majority(), council_id="council-main")
    incoming = list(good.attributed)
    if len(incoming) < 2:
        return fail(f"need >=2 dissents to drop one, got {len(incoming)}")

    good_cons = conservation(incoming, dissents_from_artifact(good.artifact), stage="synthesis")
    good_pres = presence_check(incoming, good.artifact, stage="synthesis")
    silent_on_good = good_cons.conserved and good_pres.ok
    if not silent_on_good:
        return fail(
            f"good state fired: conserved={good_cons.conserved} presence={good_pres.ok}"
        )

    victim = incoming[0]
    dropped = drop_dissent(good.artifact, victim.id)
    drop_cons = conservation(incoming, dissents_from_artifact(dropped), stage="synthesis")
    fired_on_drop = (not drop_cons.conserved) and victim.id in drop_cons.lost_ids
    if not fired_on_drop:
        return fail(
            f"planted drop did not break conservation lost={drop_cons.lost_ids} "
            f"conserved={drop_cons.conserved}"
        )
    if victim.claim in json.dumps(dropped, ensure_ascii=False) and victim.id in (
        dropped.get("minority_report") or {}
    ).get("dissent_ids", []):
        return fail("drop mutant still carries the victim id and claim")

    summarised = summarise_away(good.artifact, victim.id)
    sum_cons = conservation(incoming, dissents_from_artifact(summarised), stage="synthesis")
    sum_pres = presence_check(incoming, summarised, stage="synthesis")
    # Counts may still match (id kept, claim rewritten). Presence MUST fail.
    if not sum_cons.conserved:
        # id-preserving summarise should keep counts; if not, still require presence fail
        pass
    if sum_pres.ok:
        return fail("summarised-away mutant still passed presence (claim treated as surviving)")
    reasons = {f.dissent_id: f.reason for f in sum_pres.failures}
    if victim.id not in reasons:
        return fail(f"presence failures missed victim {reasons}")
    if victim.claim in json.dumps(summarised, ensure_ascii=False):
        return fail("summarised mutant still contains verbatim distinctive claim")

    both_states_ok = silent_on_good and fired_on_drop and (not sum_pres.ok)
    if not both_states_ok:
        return fail("both-states control did not discriminate")

    print(
        json.dumps(
            {
                "probe": "probe2-planted-drop",
                "unit_id": UNIT,
                "pass": True,
                "reviewer_starts_from_tests": True,
                "spec_anchor": "_USER-PROMPTS.md:11340 / catalog tests_required spec 11342 planted-drop",
                "good": {
                    "conserved": good_cons.conserved,
                    "presence_ok": good_pres.ok,
                    "silent": silent_on_good,
                    "in_count": good_cons.in_count,
                    "out_count": good_cons.out_count,
                },
                "planted_drop": {
                    "dropped_id": victim.id,
                    "conserved": drop_cons.conserved,
                    "lost_ids": drop_cons.lost_ids,
                    "fired": fired_on_drop,
                },
                "summarised_away": {
                    "presence_ok": sum_pres.ok,
                    "failures": [f.to_dict() for f in sum_pres.failures],
                    "counts_still_match": sum_cons.conserved,
                },
                "both_states": {
                    "silent_on_good": silent_on_good,
                    "fires_on_drop": fired_on_drop,
                    "fires_on_summarised_away": not sum_pres.ok,
                },
            },
            indent=2,
        )
    )
    print("SUCCESS:IMP-0312-probe2 planted-drop and summarised-away both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
