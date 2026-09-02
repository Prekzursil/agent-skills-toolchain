#!/usr/bin/env python3
"""Probe 2: negatives stay out of the census; plants are excluded from live.

A test with an assertion, a skipif(False), a runtime skipif, an xfail(False),
and a conditional xfail must not appear in the matching buckets. Planted
fixtures must not leak into the live union. A two-state splice that adds an
assert must drop the assertionless classification (detector is not a constant).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from detectors.two_state import VERDICT_DIFFERS, run_two_state  # noqa: E402
from testinfra.noop_census import (  # noqa: E402
    SHAPE_ALWAYS_XFAIL,
    SHAPE_ASSERTIONLESS,
    SHAPE_UNCONDITIONAL_SKIP,
    census_path,
    census_noop_tests,
    classify_module,
)

NEGATIVE = HERE / "fixtures" / "test_negative_controls.py"
PLANTED = HERE / "fixtures" / "test_planted_noop_shapes.py"


def _names(rows: list[dict], shape: str) -> set[str]:
    return {r["name"] for r in rows if shape in r.get("shapes", [])}


def main() -> int:
    neg = census_path(NEGATIVE, rel=NEGATIVE.name)
    planted = census_path(PLANTED, rel=PLANTED.name)
    live_doc = census_noop_tests(REPO)
    live_union = set(live_doc["live"]["union"])
    planted_union = set(live_doc["planted"]["union"])

    asserting = "test_negative_has_assertion_tst0126"
    skipif_false = "test_negative_skipif_false_tst0126"
    skipif_expr = "test_negative_skipif_expr_tst0126"
    xfail_false = "test_negative_xfail_false_tst0126"
    xfail_expr = "test_negative_xfail_expr_tst0126"
    raises = "test_negative_raises_can_fail_tst0126"

    neg_assert = _names(neg, SHAPE_ASSERTIONLESS)
    neg_skip = _names(neg, SHAPE_UNCONDITIONAL_SKIP)
    neg_xfail = _names(neg, SHAPE_ALWAYS_XFAIL)
    neg_all = {r["name"] for r in neg}

    negatives_clean = (
        asserting in neg_all
        and raises in neg_all
        and skipif_false in neg_all
        and skipif_expr in neg_all
        and xfail_false in neg_all
        and xfail_expr in neg_all
        and asserting not in neg_assert
        and raises not in neg_assert
        and skipif_false not in neg_skip
        and skipif_expr not in neg_skip
        and xfail_false not in neg_xfail
        and xfail_expr not in neg_xfail
    )
    plants_excluded_from_live = live_union.isdisjoint(planted_union) and bool(planted_union)

    def check(state: str) -> dict:
        source = PLANTED.read_text(encoding="utf-8")
        if state == "good":
            source = source.replace(
                "def test_planted_assertionless_tst0126():\n    value = 1 + 1\n    return {\"value\": value}\n",
                "def test_planted_assertionless_tst0126():\n    assert 1 + 1 == 2\n",
            )
        rows = classify_module(source, PLANTED.name)
        fired = "test_planted_assertionless_tst0126" in _names(rows, SHAPE_ASSERTIONLESS)
        return {"fired": fired, "payload": {"state": state, "fired": fired}}

    control = run_two_state(check, detector_id="TST-0126-probe2-assert-splice")
    ok = (
        negatives_clean
        and plants_excluded_from_live
        and control.verdict == VERDICT_DIFFERS
        and "test_planted_assertionless_tst0126" in _names(planted, SHAPE_ASSERTIONLESS)
    )
    payload = {
        "probe": "probe2-negatives-and-live-exclusion",
        "unit_id": "TST-0126",
        "pass": ok,
        "negatives_clean": negatives_clean,
        "plants_excluded_from_live": plants_excluded_from_live,
        "negative_assertionless": sorted(neg_assert),
        "negative_unconditional_skip": sorted(neg_skip),
        "negative_always_xfail": sorted(neg_xfail),
        "live_union_count": len(live_union),
        "planted_union_count": len(planted_union),
        "two_state": control.to_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:TST-0126-probe2 negatives leaked or plants entered live union")
        return 1
    print(
        "SUCCESS:TST-0126-probe2 negatives clean; plants excluded from live; "
        "assert-splice two-state differs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
