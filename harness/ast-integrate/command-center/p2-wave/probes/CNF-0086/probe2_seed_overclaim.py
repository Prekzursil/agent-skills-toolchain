#!/usr/bin/env python3
"""Probe 2: DETECTOR CONTROL — changed seed + overclaim on known-broken fixture.

A reviewer who only re-reads the artifact has verified nothing. This probe
re-runs the controls against the live replay engine.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import replay as R  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0086-council-replay.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0086-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0086" not in json.dumps(doc):
        return fail("sentinel absent")

    t_tied = R.load_transcript("tied.json")
    t_over = R.load_transcript("overclaim.json")
    t_maj = R.load_transcript("majority.json")

    seed = R.seed_control(t_tied, 7, 1)
    print(
        json.dumps(
            {
                "tied_seed_control": {
                    "outcome_changed": seed["outcome_changed"],
                    "recommendation_changed": seed["recommendation_changed"],
                    "a": seed["a_recommendation"],
                    "b": seed["b_recommendation"],
                    "ignore_hides": seed["seed_ignored_mutant_hides_change"],
                }
            },
            sort_keys=True,
        )
    )
    if not seed["outcome_changed"]:
        return fail("changed seed did not change tied outcome (seed-ignored?)")
    if not seed["recommendation_changed"]:
        return fail("tied 2-2 seed 7 vs 1 did not change recommendation")
    if seed["a_recommendation"] == seed["b_recommendation"]:
        return fail("recommendations equal after claimed change")
    if not seed["seed_ignored_mutant_hides_change"]:
        return fail("seed-ignored mutant still changed — detector control invalid")

    maj_seed = R.seed_control(t_maj, 42, 43)
    print(
        f"majority_seed outcome_changed={maj_seed['outcome_changed']} "
        f"recommendation_changed={maj_seed['recommendation_changed']}"
    )
    if not maj_seed["outcome_changed"]:
        return fail("majority changed-seed outcome identical (seed not consumed)")
    if maj_seed["recommendation_changed"]:
        return fail("majority 3-1 recommendation flipped with seed")

    orig = R.recorded_original(t_over)
    live = R.public_decision(R.replay(t_over, int(t_over["seed"])))
    cmp = R.compare(orig, live)
    oc = R.classify_overclaim(t_over, cmp)
    print(
        json.dumps(
            {
                "overclaim": oc,
                "first_divergent_stage": cmp["first_divergent_stage"],
                "recorded": orig["recommendation"],
                "replayed": live["recommendation"],
            },
            sort_keys=True,
        )
    )
    if cmp["recommendation_identical"]:
        return fail("known-broken overclaim fixture matched — detector dead")
    if not oc["fired"] or oc["classification"] != "overclaim":
        return fail(f"overclaim detector did not fire: {oc}")
    if cmp["first_divergent_stage"] != "synthesize":
        return fail(f"overclaim not localized to synthesize: {cmp['first_divergent_stage']}")
    if cmp["whole_run_mismatch_without_stage"]:
        return fail("overclaim reported as whole-run with no stage")

    art_seed = doc.get("seed_control") or {}
    if art_seed.get("outcome_changed") is not True or art_seed.get("proves_seed_consumed") is not True:
        return fail("artifact seed_control missing outcome_changed")
    art_oc = doc.get("overclaim") or {}
    if art_oc.get("detector_fired_on_known_broken") is not True:
        return fail("artifact overclaim detector flag false")
    if art_oc.get("classification") != "overclaim":
        return fail("artifact overclaim classification mismatch")

    print("SUCCESS:CNF-0086-probe2 seed control and overclaim detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
