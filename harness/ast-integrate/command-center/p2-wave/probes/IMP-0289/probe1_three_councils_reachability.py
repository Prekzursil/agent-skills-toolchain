#!/usr/bin/env python3
"""IMP-0289 probe 1: three councils aggregated, every dissent reachable.

Integration required by the catalog: 3 councils, all minority-report ids
reachable from the meta artifact, dissent counts in == out, and the meta
verdict is DISAGREEMENT rather than a majority average.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.topology.meta import (  # noqa: E402
    DISAGREEMENT,
    aggregate,
    check_reachability,
    collect_dissent_ids,
    collect_minority_ids,
    compare_dissent_counts,
    three_council_fixture,
)


def main() -> int:
    councils = three_council_fixture()
    if len(councils) != 3:
        print(f"FAILED:IMP-0289-probe1 expected 3 councils, got {len(councils)}")
        return 1
    expected_mr = collect_minority_ids(councils)
    expected_ds = collect_dissent_ids(councils)
    if len(expected_mr) < 3:
        print(f"FAILED:IMP-0289-probe1 need >=3 minority reports, got {expected_mr}")
        return 1
    meta = aggregate(councils)
    reach = check_reachability(meta, expected_mr)
    counts = compare_dissent_counts(meta, councils)
    verdict = meta.get("meta_verdict")
    averaged_away = verdict == "ADOPT" and meta.get("irreducible_disagreement") is False
    print(
        json.dumps(
            {
                "council_ids": [c["council_id"] for c in councils],
                "verdicts": [c["verdict"] for c in councils],
                "histogram": meta.get("verdict_histogram"),
                "meta_verdict": verdict,
                "irreducible_disagreement": meta.get("irreducible_disagreement"),
                "expected_minority_ids": expected_mr,
                "reachable_ids": reach.get("reachable_ids"),
                "missing_ids": reach.get("missing_ids"),
                "dissents_in": counts.get("dissents_in"),
                "dissents_out": counts.get("dissents_out"),
                "minority_in": counts.get("minority_in"),
                "minority_out": counts.get("minority_out"),
                "reach_ok": reach.get("ok"),
                "counts_ok": counts.get("ok"),
            },
            sort_keys=True,
        )
    )
    if averaged_away:
        print("FAILED:IMP-0289-probe1 majority average erased disagreement")
        return 1
    if verdict != DISAGREEMENT:
        print(f"FAILED:IMP-0289-probe1 expected DISAGREEMENT, got {verdict!r}")
        return 1
    if not reach.get("ok") or reach.get("missing_ids"):
        print(f"FAILED:IMP-0289-probe1 unreachable {reach.get('missing_ids')}")
        return 1
    if set(reach.get("reachable_ids") or []) != set(expected_mr):
        print("FAILED:IMP-0289-probe1 reachable set != expected minority ids")
        return 1
    if not counts.get("ok"):
        print(
            "FAILED:IMP-0289-probe1 dissent count mismatch "
            f"in={counts.get('dissents_in')} out={counts.get('dissents_out')} "
            f"only_in={counts.get('dissents_only_in')}"
        )
        return 1
    if counts.get("dissents_in") != len(expected_ds):
        print("FAILED:IMP-0289-probe1 incoming dissent census drifted")
        return 1
    print(
        "SUCCESS:IMP-0289-probe1 three councils aggregated, "
        f"all {len(expected_mr)} dissents reachable, counts in==out, "
        "verdict=DISAGREEMENT"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
