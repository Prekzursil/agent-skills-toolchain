#!/usr/bin/env python3
"""Probe 2: negative control (no tests) + popularity invariance.

Mechanically different from probe 1 (which recomputes from stored components):
this probe clones the fixture, strips tests, and injects popularity fields.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.quality_score import (  # noqa: E402
    EXCLUDED_INPUT_KEYS,
    compute_score,
    default_fixture_path,
    load_measurements,
    with_excluded_inputs,
    without_tests,
)


def main() -> int:
    base = load_measurements(default_fixture_path())
    with_tests = compute_score(base)
    no_tests = compute_score(without_tests(base))
    popular = compute_score(
        with_excluded_inputs(
            base,
            {
                "popularity": 10**12,
                "downloads": 10**12,
                "stars": 10**9,
                "weekly_downloads": 888888,
            },
        )
    )
    kwarg_popular = compute_score(base, popularity=10**12, downloads=42)

    lower = no_tests.score_bp < with_tests.score_bp
    invariant = (
        popular.score_bp == with_tests.score_bp
        and kwarg_popular.score_bp == with_tests.score_bp
        and popular.components_bp == with_tests.components_bp
        and popular.auditable_input_sha256 == with_tests.auditable_input_sha256
    )
    test_terms_zero = (
        no_tests.components_bp["test_presence"] == 0
        and no_tests.components_bp["test_pass_rate"] == 0
    )
    popularity_not_a_component = all(
        key not in with_tests.components_bp and key not in with_tests.weights_bp
        for key in ("popularity", "downloads", "stars")
    )

    payload = {
        "probe": "probe2-negative-controls",
        "unit_id": "IMP-0094",
        "with_tests_score_bp": with_tests.score_bp,
        "no_tests_score_bp": no_tests.score_bp,
        "no_tests_strictly_lower": lower,
        "test_terms_zero_when_absent": test_terms_zero,
        "popularity_score_bp": popular.score_bp,
        "popularity_invariant": invariant,
        "popularity_not_a_component": popularity_not_a_component,
        "excluded_inputs_named": sorted(EXCLUDED_INPUT_KEYS),
        "delta_bp": with_tests.score_bp - no_tests.score_bp,
        "pass": lower and invariant and test_terms_zero and popularity_not_a_component,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not lower:
        print("FAILED:IMP-0094-probe2 no-tests did not score strictly lower")
        return 1
    if not test_terms_zero:
        print("FAILED:IMP-0094-probe2 absent tests were not scored as zero")
        return 1
    if not invariant or not popularity_not_a_component:
        print("FAILED:IMP-0094-probe2 popularity changed the score")
        return 1
    print(
        f"no_tests={no_tests.score_bp} < with_tests={with_tests.score_bp} "
        f"popularity_invariant={invariant}"
    )
    print("SUCCESS:IMP-0094-probe2 no-tests lower; popularity invariant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
