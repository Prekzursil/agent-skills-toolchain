#!/usr/bin/env python3
"""TST-0348 probe1: both-states + planted/known-good measure + coverage recompute."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOL = REPO / "tools/vacuous-test-detector"
sys.path.insert(0, str(TOOL))

from vacuous_detector import VACUOUS_CLASSES, detect, scan_roots  # noqa: E402

PROBE_DIR = Path(__file__).resolve().parent
OUT = PROBE_DIR / "measure.json"

PLANTED = TOOL / "fixtures/planted_vacuous"
KNOWN_GOOD = TOOL / "fixtures/known_good"
BROKEN = TOOL / "fixtures/both_states/broken"
FIXED = TOOL / "fixtures/both_states/fixed"


def main() -> int:
    broken_hits = detect(BROKEN)
    fixed_hits = detect(FIXED)
    both_states = {
        "broken_fires": bool(broken_hits),
        "fixed_silent": not bool(fixed_hits),
        "broken_findings": broken_hits,
        "fixed_findings": fixed_hits,
        "pass": bool(broken_hits) and not bool(fixed_hits),
    }

    planted = scan_roots([PLANTED], repo=REPO).to_dict()
    known_good = scan_roots([KNOWN_GOOD], repo=REPO).to_dict()
    combined = scan_roots([PLANTED, KNOWN_GOOD], repo=REPO).to_dict()

    planted_classes = {f["vacuous_class"] for f in planted["findings"]}
    planted_complete = set(VACUOUS_CLASSES) <= planted_classes
    known_good_fp = len(known_good["findings"])

    ok = (
        both_states["pass"]
        and planted_complete
        and known_good_fp == 0
        and combined["vacuous_test_count"] > 0
        and combined["coverage_excluding_vacuous_pct"]
        < combined["headline_coverage_pct"]
    )

    payload = {
        "ok": ok,
        "both_states": both_states,
        "planted": {
            "class_counts": planted["class_counts"],
            "classes_detected": sorted(planted_classes),
            "all_classes_detected": planted_complete,
            "file_line_list": planted["file_line_list"],
            "findings": planted["findings"],
        },
        "known_good": {
            "tests_scanned": known_good["tests_scanned"],
            "false_positives": known_good_fp,
            "findings": known_good["findings"],
        },
        "coverage": {
            "headline_test_count": combined["headline_test_count"],
            "vacuous_test_count": combined["vacuous_test_count"],
            "non_vacuous_test_count": combined["non_vacuous_test_count"],
            "headline_coverage_pct": combined["headline_coverage_pct"],
            "coverage_excluding_vacuous_pct": combined[
                "coverage_excluding_vacuous_pct"
            ],
            "note": (
                "Equal-weight per test: headline assumes 100% of collected tests "
                "contribute; coverage_excluding_vacuous_pct is the share that "
                "actually asserts something (the number that matters)."
            ),
        },
    }
    OUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"ok": ok, "path": str(OUT.relative_to(REPO))}, indent=2))
    print("--- both-states ---")
    print(
        f"broken_fires={both_states['broken_fires']} "
        f"fixed_silent={both_states['fixed_silent']} "
        f"pass={both_states['pass']}"
    )
    print("--- planted classes ---")
    print(json.dumps(planted["class_counts"], sort_keys=True))
    print("--- coverage ---")
    print(
        f"headline={combined['headline_coverage_pct']}% "
        f"excl_vacuous={combined['coverage_excluding_vacuous_pct']}% "
        f"vacuous_tests={combined['vacuous_test_count']}/"
        f"{combined['headline_test_count']}"
    )
    print(f"known_good_fp={known_good_fp} planted_complete={planted_complete}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
