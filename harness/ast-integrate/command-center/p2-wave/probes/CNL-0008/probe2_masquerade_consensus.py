#!/usr/bin/env python3
"""Probe 2: budget exhaustion cannot masquerade as consensus.

Independent adversarial reviewer (does not read probe 1's pass/fail):
  * plant HARD-STOP exhausted AND remaining speakers agree
  * claim CONSENSUS → masquerade detector must FIRE
  * known-good unanimous council → SILENT (negative control)
  * every dial's wrong-choice policy must be observable

Signal 1: masquerade_fires(claimed, state) boolean.
Signal 2: corrupt vs declared stopping_set length / markers (different field).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import semantics as S  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0008-budget-block-12-dials-and-the-exhaustion-semantics.md"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0008-probe2 {msg}")
    return 1


def main() -> int:
    planted = S.fixture_for("turns")
    planted_v = S.evaluate(planted)
    fired = S.masquerade_fires("CONSENSUS", planted)
    if planted_v.reason != "BUDGET_EXHAUSTED":
        return fail(f"planted reason={planted_v.reason}")
    if planted_v.agreement is not True:
        return fail("planted bait is not agreement — fixture does not test masquerade")
    if fired is not True:
        return fail("masquerade detector SILENT on planted-bad (turns exhausted + agree)")

    good = S.known_good_consensus()
    good_v = S.evaluate(good)
    silent = S.masquerade_fires("CONSENSUS", good)
    if good_v.reason != "CONSENSUS":
        return fail(f"known-good reason={good_v.reason}")
    if silent is not False:
        return fail("masquerade detector FIRED on known-good (false positive)")

    negative_control = {
        "check": "masquerade_fires(claimed=CONSENSUS, state)",
        "state_it_rejects": (
            "HARD-STOP dial exhausted AND remaining speakers agree, claimed CONSENSUS"
        ),
        "planted_bad": {
            "dial": "turns",
            "evaluate.reason": planted_v.reason,
            "evaluate.agreement": planted_v.agreement,
            "claimed": "CONSENSUS",
            "fires": fired,
        },
        "known_good": {
            "evaluate.reason": good_v.reason,
            "claimed": "CONSENSUS",
            "fires": silent,
        },
        "verdict_on_state_meant_to_reject": "FIRES",
        "verdict_on_state_meant_to_accept": "SILENT",
    }
    print("NEGATIVE_CONTROL " + json.dumps(negative_control, sort_keys=True))

    corrupt_hits = []
    for dial in S.DIAL_IDS:
        w = S.run_wrong_choice(dial)
        hit = (
            w["silently_became_consensus"]
            or w["roster_shrunk"]
            or w["unrun_labelled_complete"]
            or w["depth_cap_as_answered"]
        )
        if not hit:
            return fail(f"wrong-choice for {dial} produced no observable corruption {w}")
        corrupt_hits.append(w)
        if dial in {"tool_calls", "sources", "experiments"}:
            if not w["unrun_labelled_complete"]:
                return fail(f"{dial} corrupt did not mark unrun-as-complete")
            decl = S.evaluate(S.fixture_for(dial))
            if "COVERAGE_INCOMPLETE" not in decl.markers:
                return fail(f"{dial} declared lost COVERAGE_INCOMPLETE")
        else:
            if not w["silently_became_consensus"]:
                return fail(f"{dial} wrong choice did not mint fake CONSENSUS {w}")

    if not (fired is True and silent is False):
        return fail(f"both-states fired={fired} silent={silent}")

    counterexample = {
        "claim_under_review": (
            "If remaining speakers agree after a budget binds, the stop is CONSENSUS."
        ),
        "instance": "turns cap 10/10, seats alice/bob/cara all position=A",
        "declared_reason": planted_v.reason,
        "verdict": "REFUTED",
        "reviewer_id": "CNL-0008-probe2-masquerade",
        "independent": True,
    }
    print("REVIEWER_COUNTEREXAMPLE " + json.dumps(counterexample, sort_keys=True))

    if ART.is_file() and ART.stat().st_size > 0:
        blob = ART.read_text(encoding="utf-8")
        if "masquerade" not in blob.lower():
            return fail("artifact does not record the masquerade test")
        if "SUCCESS:CNL-0008" not in blob:
            return fail("artifact sentinel absent")

    print(
        f"fired_on_bad={fired} silent_on_good={silent} "
        f"wrong_choice_hits={len(corrupt_hits)}/12"
    )
    print("SUCCESS:CNL-0008-probe2 masquerade-as-consensus both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
