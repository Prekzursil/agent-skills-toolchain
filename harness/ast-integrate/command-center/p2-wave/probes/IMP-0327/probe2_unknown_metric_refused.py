#!/usr/bin/env python3
"""IMP-0327 probe 2: independent encoding walk + unknown-metric refuse.

Starts from the tests (not the builder author's summary). Re-derives whether
each built spec's stopping tree encodes the catalog phrasing by comparing
canonical_shape against an oracle defined in THIS file from CNL-0128's five
goals. A planted unique_ideas>=1 mutant must fail that oracle.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "council" / "tests"))

from council.builder import (  # noqa: E402
    METRICS,
    build_all_owner_goals,
    canonical_shape,
)
from test_builder import (  # noqa: E402
    test_planted_weak_threshold_does_not_encode_g1,
    test_unknown_metric_refused,
)

# Oracle from CNL-0128 quoted phrasings. Not imported from goals.py.
ORACLE: dict[str, tuple] = {
    "G1": ("atom", "unique_ideas", "ge", 100),  # brainstorm until 100 unique ideas
    "G2": (  # argue until all agree or 12 rounds
        "or",
        ("atom", "rounds", "ge", 12),
        ("atom", "unanimous", "eq", True),
    ),
    "G3": (  # 90 percent consensus with a mandatory minority report
        "and",
        ("atom", "consensus_pct", "ge", 0.9),
        ("atom", "minority_report_present", "eq", True),
    ),
    "G4": ("atom", "no_new_counterexample_rounds", "ge", 2),
    "G5": ("atom", "executable_test_settled", "eq", True),
}


def _as_list(shape: tuple) -> list:
    out: list = []
    for item in shape:
        if isinstance(item, tuple):
            out.append(_as_list(item))
        else:
            out.append(item)
    return out


def main() -> int:
    unknown = test_unknown_metric_refused()
    mutant = test_planted_weak_threshold_does_not_encode_g1()
    specs = build_all_owner_goals()
    encoding_rows = []
    encoding_ok = True
    for gid, spec in specs.items():
        got = canonical_shape(spec["stopping"]["expr"])
        want = ORACLE[gid]
        match = got == want
        if not match:
            encoding_ok = False
        encoding_rows.append(
            {
                "goal_id": gid,
                "printed": spec["stopping"]["printed"],
                "got": _as_list(got),
                "want": _as_list(want),
                "encodes": match,
            }
        )

    vibe_in_registry = "vibe_score" in METRICS
    payload = {
        "probe": "probe2-unknown-metric-refused",
        "unit_id": "IMP-0327",
        "reviewer_id": "IMP-0327-probe2-encoding-oracle",
        "unknown_metric": unknown,
        "planted_weak_g1": mutant,
        "independent_encoding": {
            "rows": encoding_rows,
            "pass": encoding_ok and len(encoding_rows) == 5,
            "oracle_source": (
                "CNL-0128 question_or_target five quoted owner goals; "
                "shapes defined in this probe, not read from goals.py"
            ),
        },
        "vibe_score_absent_from_registry": not vibe_in_registry,
        "pass": bool(
            unknown["pass"]
            and mutant["pass"]
            and encoding_ok
            and not vibe_in_registry
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not payload["pass"]:
        print("FAILED:IMP-0327-probe2 unknown-metric or encoding oracle")
        return 1
    print(
        "SUCCESS:IMP-0327-probe2 unknown metric refused at named path; "
        "independent oracle encodes all five; weak unique_ideas>=1 does not encode G1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
