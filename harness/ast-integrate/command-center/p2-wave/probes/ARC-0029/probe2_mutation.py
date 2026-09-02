#!/usr/bin/env python3
"""Probe 2: remove-cap mutation must drop recall by the expected hits.

Also names (and demonstrates) a mutation the suite would NOT catch:
declared-token undercount. Independent of the author's summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from suite import (  # noqa: E402
    load_corpus,
    load_index,
    mutation_remove_cap,
    run_suite,
    undercount_mutant_still_green,
)

ART = REPO / "command-center/phase3/A4/TEST-PLAN.json"
REMOVED = "cap.secrets-scan"


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0029-probe2 TEST-PLAN.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    reviewer = doc.get("reviewer") or {}
    gap = reviewer.get("mutation_suite_would_not_catch") or {}
    if not reviewer.get("independent"):
        print("FAILED:ARC-0029-probe2 reviewer not independent")
        return 1
    if not gap.get("id") or not gap.get("mutation") or not gap.get("why_green"):
        print("FAILED:ARC-0029-probe2 named uncaught mutation missing")
        return 1

    index = load_index()
    corpus = load_corpus()
    tasks = [t for t in corpus.get("tasks") or [] if t.get("kind") == "recall"]
    flood = next(t for t in corpus.get("tasks") or [] if t.get("kind") == "flooding")

    mut = mutation_remove_cap(index, tasks, REMOVED)
    print(
        json.dumps(
            {
                "removed_id": mut["removed_id"],
                "before_hits": mut["before_hits"],
                "after_hits": mut["after_hits"],
                "expected_after_hits": mut["expected_after_hits"],
                "observed_drop": mut["observed_drop"],
                "hits_involving_removed": mut["hits_involving_removed"],
                "pass": mut["pass"],
            },
            sort_keys=True,
        )
    )
    if not mut["pass"]:
        print("FAILED:ARC-0029-probe2 mutation did not drop recall by the expected amount")
        return 1

    recorded = (doc.get("measured") or {}).get("mutation_remove") or {}
    if recorded.get("observed_drop") != mut["observed_drop"]:
        print("FAILED:ARC-0029-probe2 artifact drop drift", recorded, mut["observed_drop"])
        return 1
    if recorded.get("after_hits") != mut["after_hits"]:
        print("FAILED:ARC-0029-probe2 artifact after_hits drift")
        return 1

    under = undercount_mutant_still_green(index, flood)
    print(
        json.dumps(
            {
                "uncaught_id": gap.get("id"),
                "still_green": under["still_green"],
                "caught_by_suite": under["caught_by_suite"],
                "mutant_bounded_tokens_declared": under["mutant_bounded_tokens_declared"],
            },
            sort_keys=True,
        )
    )
    if not under["still_green"] or under["caught_by_suite"]:
        print("FAILED:ARC-0029-probe2 undercount demonstration did not stay green")
        return 1
    if gap.get("id") != "declared-token-undercount":
        print("FAILED:ARC-0029-probe2 reviewer gap id mismatch")
        return 1

    live = run_suite(index, corpus)
    if not live["pass"]:
        print("FAILED:ARC-0029-probe2 baseline suite " + ",".join(live["failures"]))
        return 1

    print(
        f"mutation_ok=True drop={mut['observed_drop']} "
        f"{mut['before_hits']}->{mut['after_hits']} "
        f"uncaught={gap.get('id')} still_green={under['still_green']}"
    )
    print("SUCCESS:ARC-0029-probe2 mutation control and named gap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
