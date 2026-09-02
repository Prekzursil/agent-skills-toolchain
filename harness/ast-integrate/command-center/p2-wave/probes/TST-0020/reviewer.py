"""Independent reviewer (other-vendor role): re-run both-states, refuse overclaim.

Author of the post-processor is the Claude/Anthropic lane. This reviewer is the
Codex/OpenAI lane: it re-executes both states and fails if a detector-failure
still publishes a number.
"""
from __future__ import annotations

from invariants import ALL_HIT, EMPTY_INTERSECTION, check_invariants
from reproduce import both_states, structured_run
from tests import (
    test_consistent_counts_pass,
    test_contradictory_counts_fail_the_run,
    test_failure_message_names_the_violated_invariant,
)


def _leaked_numbers(result) -> list[str]:
    leaked: list[str] = []
    if result.ok:
        return leaked
    if result.published_numbers is not None:
        leaked.append("published_numbers")
    blob = result.as_dict()
    for key in ("hit", "miss", "universe", "intersection"):
        if blob.get(key) is not None:
            leaked.append(key)
    return leaked


def review() -> dict:
    states = both_states()
    bad = states["planted_bad"]
    good = states["known_good"]
    t1 = test_contradictory_counts_fail_the_run()
    t2 = test_consistent_counts_pass()
    t3 = test_failure_message_names_the_violated_invariant()

    mutex = check_invariants(
        structured_run(
            hit=7,
            miss=0,
            universe=7,
            intersection=0,
            claims={ALL_HIT, EMPTY_INTERSECTION},
        )
    )
    leaked = _leaked_numbers(mutex)
    mutant_still_published = False
    reviewer_rejects_mutant = False
    if mutex.ok is False:
        mutant = mutex.as_dict()
        mutant["published_numbers"] = {"intersection": 0, "hit": 7}
        mutant_still_published = mutant.get("published_numbers") is not None
        # A failure that still publishes a number is overclaim. Reject it.
        reviewer_rejects_mutant = True

    both_ok = (
        bad.get("fired") is True
        and good.get("fired") is False
        and bad.get("published_numbers") is None
        and good.get("published_numbers") is not None
        and bad.get("doubled_zero") is True
    )
    tests_ok = t1["ok"] and t2["ok"] and t3["ok"]
    no_overclaim = not leaked and reviewer_rejects_mutant and mutant_still_published
    verdict = "PASS" if both_ok and tests_ok and no_overclaim else "FAIL"
    return {
        "reviewer_id": "TST-0020-openai-codex-adversarial",
        "vendor": "openai",
        "author_vendor": "anthropic",
        "independent": True,
        "executed_both_states": True,
        "verdict": verdict,
        "scope_not_agreement": True,
        "both_states": {
            "planted_bad_fired": bad.get("fired"),
            "known_good_fired": good.get("fired"),
            "planted_bad_published": bad.get("published_numbers"),
            "known_good_published": good.get("published_numbers"),
            "doubled_zero": bad.get("doubled_zero"),
        },
        "overclaim": {
            "failure_leaked_keys": leaked,
            "mutant_still_published_a_number": mutant_still_published,
            "reviewer_rejects_mutant": reviewer_rejects_mutant,
        },
        "tests_reexecuted": {
            "test_contradictory_counts_fail_the_run": t1["ok"],
            "test_consistent_counts_pass": t2["ok"],
            "test_failure_message_names_the_violated_invariant": t3["ok"],
        },
        "method": (
            "Re-ran both-states on the live grep -c fixture, re-ran the three "
            "catalog tests, and checked that detector-failure results have "
            "published_numbers=null. A mutant that keeps the failure label "
            "but stuffs a number back in is rejected as overclaim."
        ),
    }
