#!/usr/bin/env python3
"""IMP-0044 probe2: reviewer controls - missing fixture + always-pass probe.

Negative control 1: a probe whose known-broken fixture is absent is
UNTRUSTWORTHY with skipped=false - never silently skipped.
Reviewer requirement: the reviewer adds an always-OK probe of their own
design (returns PASS regardless of fixture bytes) and confirms it is caught.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.both_states_harness import (  # noqa: E402
    UNTRUSTWORTHY,
    bundled_fixtures,
    evaluate,
    missing_broken_control,
    reviewer_always_pass_probe,
    ProbeSpec,
)


def main() -> int:
    missing = missing_broken_control()
    broken, good = bundled_fixtures()
    reviewer_probe = evaluate(
        ProbeSpec(
            probe_id="reviewer-always-pass-shard10",
            run=reviewer_always_pass_probe,
            known_broken=broken,
            known_good=good,
        )
    )
    checks = {
        "missing_untrustworthy": missing.trust == UNTRUSTWORTHY,
        "missing_not_skipped": not missing.skipped,
        "missing_reason": missing.reason == "missing-broken-fixture",
        "reviewer_probe_caught": reviewer_probe.trust == UNTRUSTWORTHY,
        "reviewer_probe_reason": reviewer_probe.reason == "same-verdict-both-states",
        "reviewer_probe_not_skipped": not reviewer_probe.skipped,
    }
    out = {
        "probe": "probe2-missing-fixture-and-reviewer-always-pass",
        "unit_id": "IMP-0044",
        "checks": checks,
        "rows": {
            "missing-broken": {"trust": missing.trust, "reason": missing.reason,
                               "skipped": missing.skipped},
            "reviewer-always-pass": {"trust": reviewer_probe.trust,
                                     "reason": reviewer_probe.reason,
                                     "skipped": reviewer_probe.skipped},
        },
        "reviewer": {
            "reviewer_id": "IMP-0044-probe2-reviewer-always-pass",
            "requirement": "reviewer adds an always-OK probe of their own design and confirms it is caught",
            "verdict": "PASS" if all(checks.values()) else "FAIL",
            "independent": True,
        },
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    print(f"missing_flagged={checks['missing_untrustworthy']} "
          f"not_skipped={checks['missing_not_skipped']} "
          f"reviewer_probe_caught={checks['reviewer_probe_caught']}")
    if not all(checks.values()):
        failed = [k for k, v in checks.items() if not v]
        print(f"FAILED:IMP-0044-probe2 {failed}")
        return 1
    print("SUCCESS:IMP-0044-probe2 missing fixture UNTRUSTWORTHY, reviewer always-OK caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
