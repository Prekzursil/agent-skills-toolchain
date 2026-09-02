#!/usr/bin/env python3
"""Named probe 1: scale-up trigger conditions (IMP-0274).

Catalog test: unit: scale-up trigger conditions.
Grows within min/max when coverage or expertise gaps are detected; holds
otherwise; never exceeds max_seats; reports an unfilled gap instead of
silently skipping it.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.participants.elastic import (  # noqa: E402
    ElasticError,
    recruit,
    scale_decision,
)
from scenario import at_max_with_gap, base_run, covered_run  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0274-probe1 {msg}")
    return 1


def main() -> int:
    cases: list[dict] = []

    # 1. Coverage gap (security missing) at min < max → recruit exactly one.
    gap_run = base_run()
    d1 = scale_decision(gap_run)
    r1 = recruit(gap_run)
    if d1.action != "recruit" or d1.recruit_count != 1:
        return _fail(f"coverage-gap decision={d1.to_dict()}")
    if "security" not in d1.missing_tags:
        return _fail(f"security not in missing_tags {d1.missing_tags}")
    if d1.current_seats != 3 or d1.max_seats != 6:
        return _fail(f"bounds current={d1.current_seats} max={d1.max_seats}")
    if len(r1.recruited) != 1 or r1.recruited[0]["seat_id"] != "r-security":
        return _fail(f"recruited={r1.to_dict()}")
    if len(r1.run["seats"]) != 4:
        return _fail(f"seat_count={len(r1.run['seats'])}")
    if len(r1.run["seats"]) > d1.max_seats:
        return _fail("exceeded max_seats")
    rec = r1.recruited[0]
    if rec.get("original") is not False:
        return _fail("recruit marked original")
    if "running_consensus" in rec["context"]:
        return _fail("honest recruit inherited consensus")
    cases.append({"id": "coverage-gap-recruits", "pass": True, "decision": d1.to_dict()})

    # 2. No gap → hold.
    d2 = scale_decision(covered_run())
    r2 = recruit(covered_run())
    if d2.action != "hold" or d2.reason != "no_gap" or d2.recruit_count != 0:
        return _fail(f"no-gap decision={d2.to_dict()}")
    if r2.recruited:
        return _fail("no-gap recruited anyway")
    cases.append({"id": "no-gap-holds", "pass": True, "reason": d2.reason})

    # 3. At max with a still-open gap → hold, gap reported (not silent).
    d3 = scale_decision(at_max_with_gap())
    if d3.action != "hold" or d3.reason != "at_max_with_gap":
        return _fail(f"at-max decision={d3.to_dict()}")
    if not d3.unfilled_tags or "security" not in d3.unfilled_tags:
        return _fail(f"at-max unfilled silent {d3.to_dict()}")
    if d3.recruit_count != 0:
        return _fail("at-max recruited")
    cases.append({"id": "at-max-reports-gap", "pass": True, "reason": d3.reason})

    # 4. Mid-run expertise topic with capacity → recruit the covering candidate.
    topic_run = base_run()
    topic_run["seats"][2]["expertise"] = ["process", "security"]
    topic_run["mid_run_topics"] = ["cryptography"]
    d4 = scale_decision(topic_run)
    r4 = recruit(topic_run)
    if d4.action != "recruit" or "cryptography" not in d4.missing_tags:
        return _fail(f"expertise-gap decision={d4.to_dict()}")
    if len(r4.recruited) != 1 or r4.recruited[0]["seat_id"] != "r-crypto":
        return _fail(f"expertise recruited={r4.to_dict()}")
    cases.append({"id": "mid-run-expertise-gap", "pass": True, "decision": d4.to_dict()})

    # 5. Capacity cap: three missing tags, one remaining seat → recruit_count 1.
    tight = base_run(max_seats=4, required_coverage=["parser-c", "testing", "security", "cryptography"])
    d5 = scale_decision(tight)
    r5 = recruit(tight)
    if d5.recruit_count != 1:
        return _fail(f"capacity recruit_count={d5.recruit_count} decision={d5.to_dict()}")
    if len(r5.run["seats"]) != 4:
        return _fail(f"capacity seat_count={len(r5.run['seats'])}")
    cases.append(
        {
            "id": "capacity-caps-at-max",
            "pass": True,
            "recruit_count": d5.recruit_count,
            "seat_count": len(r5.run["seats"]),
        }
    )

    # 6. Gap with no covering candidate → unfilled, not a silent hold.
    barren = base_run()
    barren["candidates"] = []
    r6 = recruit(barren)
    if r6.decision.action != "unfilled":
        return _fail(f"empty-candidates action={r6.decision.action} reason={r6.decision.reason}")
    if r6.decision.reason != "gap_with_no_covering_candidate":
        return _fail(f"empty-candidates reason={r6.decision.reason}")
    if r6.recruited:
        return _fail("empty-candidates recruited")
    cases.append({"id": "unfilled-gap-is-loud", "pass": True, "reason": r6.decision.reason})

    # 7. Bounds fail closed.
    bad = base_run(min_seats=5, max_seats=2)
    try:
        scale_decision(bad)
        return _fail("max<min did not raise")
    except ElasticError as exc:
        if "max_seats" not in str(exc):
            return _fail(f"unexpected ElasticError {exc}")
    cases.append({"id": "bounds-fail-closed", "pass": True})

    # 8. Honest recruit does not grow past max even across two tags with room 2.
    two = base_run(required_coverage=["parser-c", "testing", "security", "cryptography"])
    r8 = recruit(two)
    if len(r8.run["seats"]) > two["max_seats"]:
        return _fail("grew past max")
    if len(r8.recruited) != 2:
        return _fail(f"two-gap recruited={len(r8.recruited)}")
    cases.append({"id": "two-gaps-two-recruits-within-max", "pass": True})

    # Deepcopy isolation: recruiting must not mutate the caller's seat list.
    source = base_run()
    before = deepcopy(source["seats"])
    recruit(source)
    if source["seats"] != before:
        return _fail("recruit mutated caller seats")
    cases.append({"id": "no-caller-mutation", "pass": True})

    print(
        json.dumps(
            {
                "probe": "probe1-scale-up-triggers",
                "unit_id": "IMP-0274",
                "pass": True,
                "cases": cases,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0274-probe1 scale-up trigger conditions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
