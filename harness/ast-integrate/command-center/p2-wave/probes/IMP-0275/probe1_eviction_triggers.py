"""Named probe 1: eviction triggers and quorum recomputation.

Catalog test: unit — eviction triggers and quorum recomputation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.participants.replace import (  # noqa: E402
    compute_quorum,
    evaluate_triggers,
    evict,
    find_eviction_candidates,
    make_run,
    record_failure,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0275-probe1 {msg}")
    return 1


def main() -> int:
    idle_run = make_run()
    dave = next(p for p in idle_run["participants"] if p["id"] == "dave")
    alice = next(p for p in idle_run["participants"] if p["id"] == "alice")
    idle = evaluate_triggers(dave, idle_run["now"], idle_run["policy"])
    healthy = evaluate_triggers(alice, idle_run["now"], idle_run["policy"])
    if not idle["due"] or idle["reasons"] != ["inactivity"]:
        return fail(f"inactivity trigger silent: {idle}")
    if healthy["due"]:
        return fail(f"false positive on active seat: {healthy}")
    cand = {c["id"] for c in find_eviction_candidates(idle_run)}
    if cand != {"dave"}:
        return fail(f"candidate set {cand}")

    after_idle = evict(idle_run, "dave")
    q1 = after_idle["quorum"]
    if q1 != compute_quorum(after_idle):
        return fail("recorded quorum diverges from independent recompute")
    if q1["seated_count"] != 3 or not q1["ok"] or q1["void"]:
        return fail(f"quorum after inactivity eviction: {q1}")
    if "dave" in q1["seated_ids"] or "dave" not in q1["evicted_ids"]:
        return fail(f"dave still occupies a seat: {q1}")

    fail_run = make_run(dave_last_activity_at=190, carol_failures=3)
    carol = next(p for p in fail_run["participants"] if p["id"] == "carol")
    fail_trig = evaluate_triggers(carol, fail_run["now"], fail_run["policy"])
    if not fail_trig["due"] or fail_trig["reasons"] != ["repeated_failure"]:
        return fail(f"repeated-failure trigger silent: {fail_trig}")
    after_fail = evict(fail_run, "carol")
    if after_fail["quorum"]["seated_count"] != 3 or not after_fail["quorum"]["ok"]:
        return fail(f"quorum after failure eviction: {after_fail['quorum']}")

    stacked = record_failure(make_run(dave_last_activity_at=100), "dave", now=200)
    stacked_dave = next(p for p in stacked["participants"] if p["id"] == "dave")
    stacked_trig = evaluate_triggers(stacked_dave, 200, stacked["policy"])
    if stacked_trig["due"] or "inactivity" in stacked_trig["reasons"]:
        return fail(f"failure incorrectly stacked with inactivity: {stacked_trig}")

    two = make_run(carol_failures=3)
    two = evict(two, "dave")
    two = evict(two, "carol")
    if not two["quorum"]["void"] or two["quorum"]["seated_count"] != 2:
        return fail(f"expected void quorum after two evictions: {two['quorum']}")
    restored = evict(
        evict(make_run(carol_failures=3), "dave"),
        "carol",
        replacement={"id": "evan"},
    )
    if restored["quorum"]["seated_count"] != 3 or not restored["quorum"]["ok"]:
        return fail(f"replacement did not restore quorum: {restored['quorum']}")
    if "evan" not in restored["quorum"]["seated_ids"]:
        return fail("replacement not seated")
    evan_prior = [c for c in restored["contributions"] if c.get("author_id") == "evan"]
    if evan_prior:
        return fail("replacement inherited contributions")

    payload = {
        "inactivity_due": True,
        "pass": True,
        "probe": "probe1-eviction-triggers-quorum",
        "quorum_after_inactivity_eviction": q1["seated_count"],
        "quorum_void_after_two_evictions": True,
        "repeated_failure_due": True,
        "replacement_restored_quorum": True,
        "unit_id": "IMP-0275",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "inactivity=True repeated_failure=True quorum_after=3 "
        "void_after_two=True replacement_restores=True"
    )
    print("SUCCESS:IMP-0275-probe1 eviction triggers and quorum recomputation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
