#!/usr/bin/env python3
"""Probe 2: reviewer re-runs DETECTOR CONTROL on the known-broken fixtures.

Does not re-read the conclusion. Re-executes the suite, asserts each
planted defect still fires, and runs two mutations that prove the
detector is testing the rule it claims:
  * stdlib json.loads last-wins on the duplicate-key fixture
  * additionalProperties true lets the unknown-field fixture parse
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0035-strict-parser.json"


def main() -> int:
    report = S.run_suite()
    by_id = {r["id"]: r for r in report["results"]}
    checks = [
        ("unknown-field fires", by_id["unknown-field"]["errored"] is True),
        (
            "unknown-field class",
            by_id["unknown-field"]["classification"] == "unknown-field",
        ),
        ("case-distinct fires", by_id["case-distinct"]["errored"] is True),
        (
            "case-distinct class",
            by_id["case-distinct"]["classification"] == "case-collision",
        ),
        ("duplicate-key fires", by_id["duplicate-key"]["errored"] is True),
        (
            "duplicate-key class",
            by_id["duplicate-key"]["classification"] == "duplicate-key",
        ),
        ("control silent", by_id["control"]["errored"] is False),
        (
            "lenient last-wins",
            report["permissive_duplicate"].get("name") == "last-wins-if-permissive",
        ),
        (
            "mutation additionalProperties true accepts unknown",
            report["mutation_unknown_accepted_when_additional_properties_true"]
            is True,
        ),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:CNF-0035-probe2 {name}")
            return 1
    if not ART.is_file():
        print("FAILED:CNF-0035-probe2 confirmation artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        print("FAILED:CNF-0035-probe2 reviewer verdict not PASS")
        return 1
    print("SUCCESS:CNF-0035-probe2 detector-control known-broken fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
