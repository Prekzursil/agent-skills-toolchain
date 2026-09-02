"""Catalog tests for TST-0020."""
from __future__ import annotations

from invariants import (
    ALL_HIT,
    EMPTY_INTERSECTION,
    RunOutput,
    check_invariants,
)
from reproduce import both_states, planted_bad, structured_run


def _no_number_published(result) -> bool:
    if result.published_numbers is not None:
        return False
    blob = result.as_dict()
    for key in ("hit", "miss", "universe", "intersection"):
        if key in blob and blob[key] is not None:
            return False
    return True


def test_contradictory_counts_fail_the_run() -> dict:
    """Live grep-c blob plus structured sum/subset contradictions fail the run."""
    live = planted_bad()
    sum_res = check_invariants(
        structured_run(hit=3, miss=5, universe=7, intersection=3)
    )
    subset_res = check_invariants(
        structured_run(hit=7, miss=0, universe=7, intersection=9)
    )
    well_res = check_invariants(
        RunOutput(
            counts={
                "hit": "0\n0",
                "miss": 0,
                "universe": 7,
                "intersection": 0,
            },
            claims=set(),
            raw="0\n0\n",
        )
    )

    cases = [
        (
            "live-grep-c-or-echo-0",
            live["fired"] is True
            and live["classification"] == "detector-failure"
            and live["published_numbers"] is None
            and live["doubled_zero"] is True
            and ALL_HIT in live["naive_claims"]
            and EMPTY_INTERSECTION in live["naive_claims"],
            live["violated_invariants"],
            live["message"],
        ),
        (
            "counts-must-sum",
            sum_res.ok is False
            and sum_res.classification == "detector-failure"
            and _no_number_published(sum_res)
            and "counts-must-sum" in sum_res.violated,
            sum_res.violated,
            sum_res.message,
        ),
        (
            "subset-not-gt-superset",
            subset_res.ok is False
            and subset_res.classification == "detector-failure"
            and _no_number_published(subset_res)
            and "subset-not-gt-superset" in subset_res.violated,
            subset_res.violated,
            subset_res.message,
        ),
        (
            "count-is-single-integer",
            well_res.ok is False
            and well_res.classification == "detector-failure"
            and _no_number_published(well_res)
            and "count-is-single-integer" in well_res.violated,
            well_res.violated,
            well_res.message,
        ),
    ]
    failed = [c[0] for c in cases if not c[1]]
    return {
        "id": "test_contradictory_counts_fail_the_run",
        "ok": not failed,
        "failed_cases": failed,
        "live_doubled_zero": live["doubled_zero"],
        "live_raw": live["raw_stdout"],
        "live_claims": live["naive_claims"],
        "cases": [
            {"name": c[0], "ok": c[1], "violated": c[2], "message": c[3]}
            for c in cases
        ],
    }


def test_consistent_counts_pass() -> dict:
    empty = check_invariants(
        structured_run(
            hit=0,
            miss=7,
            universe=7,
            intersection=0,
            claims={EMPTY_INTERSECTION},
        )
    )
    mixed = check_invariants(
        structured_run(hit=3, miss=4, universe=7, intersection=3)
    )
    all_hit = check_invariants(
        structured_run(
            hit=7,
            miss=0,
            universe=7,
            intersection=7,
            claims={ALL_HIT},
        )
    )
    live_good = both_states()["known_good"]
    rows = [
        ("structured-empty", empty),
        ("structured-mixed", mixed),
        ("structured-all-hit", all_hit),
    ]
    failed = []
    published = {}
    for name, res in rows:
        if (
            not res.ok
            or res.classification is not None
            or res.published_numbers is None
        ):
            failed.append(name)
        else:
            published[name] = res.published_numbers
    if live_good["fired"] or live_good["published_numbers"] is None:
        failed.append("live-corrected-grep-c")
    else:
        published["live-corrected-grep-c"] = live_good["published_numbers"]
    return {
        "id": "test_consistent_counts_pass",
        "ok": not failed,
        "failed_cases": failed,
        "published_numbers": published,
        "live_good_claims": live_good["naive_claims"],
        "live_good_raw": live_good["raw_stdout"],
    }


def test_failure_message_names_the_violated_invariant() -> dict:
    sum_res = check_invariants(
        structured_run(hit=3, miss=5, universe=7, intersection=3)
    )
    subset_res = check_invariants(
        structured_run(hit=7, miss=0, universe=7, intersection=9)
    )
    mutex_res = check_invariants(
        structured_run(
            hit=7,
            miss=0,
            universe=7,
            intersection=0,
            claims={ALL_HIT, EMPTY_INTERSECTION},
        )
    )
    rows = [
        ("counts-must-sum", sum_res),
        ("subset-not-gt-superset", subset_res),
        ("mutex-all-hit-empty-intersection", mutex_res),
    ]
    named = []
    missing = []
    for iid, res in rows:
        text = res.message
        ok = (
            res.ok is False
            and iid in res.violated
            and iid in text
            and "DETECTOR-FAILURE" in text
            and _no_number_published(res)
        )
        named.append({"invariant": iid, "ok": ok, "message": text})
        if not ok:
            missing.append(iid)
    return {
        "id": "test_failure_message_names_the_violated_invariant",
        "ok": not missing,
        "missing": missing,
        "named": named,
    }


def run_all() -> dict:
    t1 = test_contradictory_counts_fail_the_run()
    t2 = test_consistent_counts_pass()
    t3 = test_failure_message_names_the_violated_invariant()
    return {
        "ok": t1["ok"] and t2["ok"] and t3["ok"],
        "tests": [t1, t2, t3],
    }


if __name__ == "__main__":
    import json
    import sys

    out = run_all()
    print(json.dumps(out, indent=2, default=str)[:8000])
    if not out["ok"]:
        print("FAILED:TST-0020 tests")
        raise SystemExit(1)
    print("SUCCESS:TST-0020 tests")
    raise SystemExit(0)
