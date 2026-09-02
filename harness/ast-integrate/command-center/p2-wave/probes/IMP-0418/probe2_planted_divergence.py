#!/usr/bin/env python3
"""Probe 2: planted-divergence control (IMP-0418).

Mechanically different from probe 1: patch one call site to a laxer min_bytes
and require the oracle to fire. An oracle that cannot see a planted fork is
not an oracle.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from predicate_oracle import PLANTED_SITE, run_planted_divergence  # noqa: E402


def main() -> int:
    planted = run_planted_divergence()
    payload = {
        "probe": "probe2-planted-divergence",
        "unit_id": "IMP-0418",
        "baseline_agree": planted["baseline_agree"],
        "baseline_disagreements": planted["baseline_disagreements"],
        "planted_site": planted["planted_site"],
        "planted_min_bytes": planted["planted_min_bytes"],
        "planted_any_disagreement": planted["planted_any_disagreement"],
        "planted_pair_disagreement_sum": planted["planted_pair_disagreement_sum"],
        "expected_diverging_count": planted["expected_diverging_count"],
        "fired": planted["fired"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not planted["baseline_agree"] or planted["baseline_disagreements"] != 0:
        print("FAILED:IMP-0418-probe2 baseline does not agree; cannot interpret planted fork")
        return 1
    if planted["planted_site"] != PLANTED_SITE:
        print("FAILED:IMP-0418-probe2 planted site mismatch")
        return 1
    if not planted["planted_any_disagreement"]:
        print("FAILED:IMP-0418-probe2 planted laxer threshold did not fire")
        return 1
    if planted["expected_diverging_count"] < 1:
        print("FAILED:IMP-0418-probe2 no artifacts sit on the threshold (oracle too easy)")
        return 1
    if not planted["fired"]:
        print("FAILED:IMP-0418-probe2 control did not fire")
        return 1
    print(
        f"planted_site={planted['planted_site']} "
        f"diverging_artifacts={planted['expected_diverging_count']} "
        f"pair_sum={planted['planted_pair_disagreement_sum']}"
    )
    print("SUCCESS:IMP-0418-probe2 planted laxer-threshold fork fires the oracle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
