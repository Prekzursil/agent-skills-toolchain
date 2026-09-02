#!/usr/bin/env python3
"""Named probe 1: floor/ceiling enforcement and eviction handoff.

Falsifiable question: do three empty acknowledgements satisfy a minimum-
engagement floor? Metric is content units, not message count. Answer: NO.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from council.budget.engagement import (  # noqa: E402
    CEILING_BREACH,
    FLOOR_FAIL,
    INACTIVITY,
    EngagementPolicy,
    EngagementTracker,
    apply_eviction_handoff,
    demo_council_state,
    three_empty_acks_meet_floor,
)
from council.participants.replace import ballot_count  # noqa: E402

CLAIM_A = "Cite: _USER-PROMPTS.md:10928 separates speaking quotas from minimum engagement."
CLAIM_B = "Propose: emit an eviction handoff that retains prior votes and claims."
CLAIM_C = "Counterexample: three empty acknowledgements produce zero content units."


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0299-probe1 {msg}")
    return 1


def main() -> int:
    mod = TOOLS / "council" / "budget" / "engagement.py"
    if not mod.is_file() or mod.stat().st_size < 200:
        return fail("engagement.py missing")

    ack = three_empty_acks_meet_floor(EngagementPolicy(min_content_units=1))
    if ack["meets_floor"] is not False:
        return fail(f"three acks met the floor: {ack}")
    if ack["content_units"] != 0:
        return fail(f"three acks content_units={ack['content_units']} want 0")
    if ack["message_count"] != 3:
        return fail(f"three acks message_count={ack['message_count']} want 3")
    if not ack["message_count_would_pass_floor_of_1"]:
        return fail("message-count mutant did not show the load-bearing gap")
    if ack["consent_eligible"] is not False:
        return fail("filler seat was marked consent-eligible")
    if ack["answer"] != "NO":
        return fail(f"falsifiable answer {ack['answer']!r} want NO")

    policy = EngagementPolicy(
        min_content_units=1,
        max_content_units=2,
        max_consecutive_empty_turns=2,
    )
    engaged = EngagementTracker(policy, {"p-good": "seat-good"})
    r1 = engaged.record_turn("p-good", CLAIM_A, round_no=1)
    if not r1.accepted or r1.content_units_added < 1:
        return fail(f"substantive turn rejected: {r1}")
    if not engaged.status("p-good")["meets_floor"]:
        return fail("one claim failed a floor of 1")

    ceil = EngagementTracker(policy, {"p-max": "seat-max"})
    a = ceil.record_turn("p-max", CLAIM_A, round_no=1)
    b = ceil.record_turn("p-max", CLAIM_B, round_no=1)
    c = ceil.record_turn("p-max", CLAIM_C, round_no=1)
    if not a.accepted or not b.accepted:
        return fail("quota of 2 refused the first two claims")
    if c.accepted:
        return fail("third claim was accepted over a ceiling of 2")
    if c.handoff is None or c.handoff.reason != CEILING_BREACH:
        return fail(f"ceiling handoff missing: {c}")
    if ceil.status("p-max")["content_units"] != 2:
        return fail("ceiling path mutated the recorded unit count")
    if ceil.status("p-max")["message_count"] != 2:
        return fail("refused turn was counted as a message")

    idle = EngagementTracker(policy, {"p-idle": "seat-idle"})
    idle.record_turn("p-idle", "ok", round_no=1)
    idle.record_turn("p-idle", "ack", round_no=1)
    third = idle.record_turn("p-idle", "thanks", round_no=1)
    if third.handoff is None or third.handoff.reason != INACTIVITY:
        return fail(f"inactivity handoff missing after 3 empty turns: {third}")

    silent = EngagementTracker(policy, {"p-silent": "seat-silent"})
    silent.note_silent_round("p-silent", round_no=1)
    silent.note_silent_round("p-silent", round_no=2)
    s3 = silent.note_silent_round("p-silent", round_no=3)
    if s3.handoff is None or s3.handoff.reason != INACTIVITY:
        return fail("silent rounds did not trip inactivity")
    if silent.status("p-silent")["message_count"] != 0:
        return fail("silence was counted as a message")

    filler = EngagementTracker(policy, {"ack-bot": "seat-critic"})
    filler.record_turn("ack-bot", "ok")
    filler.record_turn("ack-bot", "ack")
    filler.record_turn("ack-bot", "thanks")
    floors = filler.evaluate_checkpoint(["ack-bot"])
    if not floors or floors[0].reason != FLOOR_FAIL:
        return fail(f"filler checkpoint did not emit FLOOR_FAIL: {floors}")
    if floors[0].consent_eligible:
        return fail("floor-fail handoff left consent_eligible true")

    census_before = filler.status("ack-bot")
    state = demo_council_state(filler_occupant="ack-bot", seat_id="seat-critic")
    prior = ballot_count(state, "ack-bot")
    if prior < 1:
        return fail("demo state has no prior ballot to retain")
    applied = apply_eviction_handoff(
        state,
        floors[0],
        {
            "persona_id": "persona-critic-replacement",
            "role": "critic",
            "script": {},
        },
        inherit_votes=False,
    )
    if not applied["prior_contributions_retained"]:
        return fail(f"eviction dropped prior contributions: {applied}")
    if applied["departed_ballots_after"] != applied["departed_ballots_before"]:
        return fail("departed ballot count changed")
    if applied["replacement_ballot_count"] != 0:
        return fail("replacement inherited ballots on the production path")
    if applied["departed_status"] != "departed":
        return fail(f"departed status={applied['departed_status']}")
    if applied["replacement_occupant_id"] == "ack-bot":
        return fail("replacement reused the departed occupant_id")
    if applied["departed_ideas_after"] != applied["departed_ideas_before"]:
        return fail("ideas were dropped on eviction")

    payload = {
        "probe": "probe1-floor-ceiling-eviction",
        "unit_id": "IMP-0299",
        "pass": True,
        "falsifiable": {
            "question": ack["question"],
            "answer": ack["answer"],
            "meets_floor": ack["meets_floor"],
            "content_units": ack["content_units"],
            "message_count": ack["message_count"],
        },
        "ceiling_refused_third_claim": True,
        "inactivity_fired": True,
        "floor_fail_on_filler": True,
        "eviction": {
            "prior_ballots": applied["departed_ballots_after"],
            "replacement_ballots": applied["replacement_ballot_count"],
            "retained": applied["prior_contributions_retained"],
        },
        "filler_census": census_before,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "three_acks meets_floor=False content_units="
        f"{ack['content_units']} message_count={ack['message_count']}"
    )
    print(
        "eviction retained_ballots="
        f"{applied['departed_ballots_after']} replacement_ballots="
        f"{applied['replacement_ballot_count']}"
    )
    print("SUCCESS:IMP-0299-probe1 floor/ceiling enforcement and eviction handoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
