"""IMP-0275 / TST-0278: eviction triggers, quorum, and retention tests.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/participants/tests/test_replace.py
Also runs under pytest. Exit 0 iff all ten tests pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

PARENT = Path(__file__).resolve().parent.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

from replace import (  # noqa: E402
    census_retention_check,
    compute_quorum,
    compute_tally,
    contribution_census,
    evict,
    evaluate_triggers,
    find_eviction_candidates,
    make_run,
    record_failure,
)


def test_inactivity_trigger_and_no_false_positive():
    run = make_run(dave_last_activity_at=140)
    dave = next(p for p in run["participants"] if p["id"] == "dave")
    assert evaluate_triggers(dave, run["now"], run["policy"])["reasons"] == ["inactivity"]
    alice = next(p for p in run["participants"] if p["id"] == "alice")
    assert evaluate_triggers(alice, run["now"], run["policy"])["due"] is False


def test_repeated_failure_trigger():
    run = make_run(carol_failures=3)
    carol = next(p for p in run["participants"] if p["id"] == "carol")
    trig = evaluate_triggers(carol, run["now"], run["policy"])
    assert trig["due"] is True and "repeated_failure" in trig["reasons"]


def test_failure_is_activity_so_inactivity_does_not_stack():
    run = make_run(dave_last_activity_at=140)
    run = record_failure(run, "dave", 260)
    dave = next(p for p in run["participants"] if p["id"] == "dave")
    trig = evaluate_triggers(dave, 260, run["policy"])
    assert trig["due"] is False  # fresh failure refreshed last_activity_at


def test_eviction_triggers_and_quorum_recomputation():
    run = make_run(dave_last_activity_at=140)
    due = find_eviction_candidates(run)
    assert [c["id"] for c in due] == ["dave"]
    after = evict(run, "dave")
    q = compute_quorum(after)
    assert q["seated_count"] == 3 and q["ok"] is True and q["evicted_ids"] == ["dave"]


def test_second_eviction_voids_quorum_replacement_restores():
    run = make_run(dave_last_activity_at=140, carol_failures=3)
    one = evict(run, "dave")
    two = evict(one, "carol")
    assert compute_quorum(two)["void"] is True
    three = evict(two, "carol", replacement={"id": "erin", "role": "critic"})
    q = compute_quorum(three)
    assert q["seated_count"] == 3 and q["ok"] is True and "erin" in q["seated_ids"]


def test_refuse_eviction_without_trigger():
    run = make_run(dave_last_activity_at=200)  # everyone fresh: no trigger due
    assert find_eviction_candidates(run) == []
    fresh = evict(run, "dave")  # no trigger, no replacement: seat simply opens
    assert compute_quorum(fresh)["seated_count"] == 3


def test_replacement_does_not_inherit_and_quorum_helper_matches():
    run = make_run(dave_last_activity_at=140)
    after = evict(run, "dave", replacement={"id": "erin", "role": "scribe"})
    assert compute_quorum(after) == after["quorum"]
    erin = next(p for p in after["participants"] if p["id"] == "erin")
    assert erin["failures"] == 0 and erin["last_activity_at"] == after["now"]
    ids = {c["author_id"] for c in after["contributions"]}
    assert "erin" not in ids  # no inherited authorship


def test_prior_votes_and_ideas_retained():
    run = make_run(dave_last_activity_at=140)
    after = evict(run, "dave")
    before = contribution_census(run)
    kept = contribution_census(after)
    assert kept["by_author"]["dave"] == before["by_author"]["dave"]
    assert census_retention_check(before, kept)["ok"] is True


def test_negative_control_drop_evicted_ideas_fails_census():
    run = make_run(dave_last_activity_at=140)
    after = evict(run, "dave")
    pruned = {k: (dict(v) if k == "by_author" else v) for k, v in contribution_census(after).items()}
    pruned["by_author"]["dave"] = [i for i in pruned["by_author"]["dave"] if not i.startswith("i-")]
    res = census_retention_check(contribution_census(run), pruned)
    assert res["ok"] is False and res["missing"], "dropping evicted ideas must FAIL the census"


def test_tally_matches_documented_eviction_rule():
    run = make_run(dave_last_activity_at=140)
    after = evict(run, "dave")
    tally = compute_tally(after)
    assert tally == after["tally"]
    assert tally["rule_id"] == "R-EVICT-RETAIN"
    assert tally["closed_rounds"]["1"]["includes_evicted"] == ["dave"]
    open_round = tally["open_round"]
    assert open_round["counts"]["yes"] == 3
    assert [c["author_id"] for c in open_round["excluded_evicted"]] == ["dave"]


TESTS = [
    test_eviction_triggers_and_quorum_recomputation,
    test_failure_is_activity_so_inactivity_does_not_stack,
    test_inactivity_trigger_and_no_false_positive,
    test_negative_control_drop_evicted_ideas_fails_census,
    test_prior_votes_and_ideas_retained,
    test_refuse_eviction_without_trigger,
    test_repeated_failure_trigger,
    test_replacement_does_not_inherit_and_quorum_helper_matches,
    test_second_eviction_voids_quorum_replacement_restores,
    test_tally_matches_documented_eviction_rule,
]

if __name__ == "__main__":
    failed = []
    for t in TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed.append(t.__name__)
            print(f"FAIL {t.__name__}: {exc}")
    print(f"ran={len(TESTS)}")
    if failed:
        print(f"FAILED:IMP-0275-tests {failed}")
        raise SystemExit(1)
    print("SUCCESS:IMP-0275-tests all eviction/retention tests pass")
