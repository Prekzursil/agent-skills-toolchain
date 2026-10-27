#!/usr/bin/env python3
"""Probe 1: python vs javascript reducers, byte-identical on a malformed corpus."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from differential import run_differential  # noqa: E402


def main() -> int:
    report = run_differential()
    required_classes = {"healthy", "partial-artifact", "missing-sentinel", "torn-json"}
    present = set(report["classes"])
    missing_cls = sorted(required_classes - present)
    fail = False
    reasons: list[str] = []
    if report["corpus_size"] < 12:
        fail = True
        reasons.append(f"corpus_size {report['corpus_size']} < 12")
    if report["malformed_count"] < 3:
        fail = True
        reasons.append(
            f"malformed_count {report['malformed_count']} < 3 "
            "(zero disagreements without malformed inputs is not a result)"
        )
    if missing_cls:
        fail = True
        reasons.append(f"missing classes {missing_cls}")
    if report["disagreement_count"] != 0:
        fail = True
        reasons.append(f"disagreements={report['disagreement_count']}")
    if not report["byte_identical"]:
        fail = True
        reasons.append("byte_identical=false")
    if report["python_count"] != report["corpus_size"]:
        fail = True
        reasons.append("python result count != corpus")
    if report["monitor_count"] != report["corpus_size"]:
        fail = True
        reasons.append("monitor result count != corpus")

    payload = {
        "probe": "probe1-corpus-parity",
        "unit_id": "TST-0330",
        "pass": not fail,
        "corpus_size": report["corpus_size"],
        "malformed_count": report["malformed_count"],
        "disagreement_count": report["disagreement_count"],
        "disagreements": report["disagreements"],
        "classes": report["classes"],
        "byte_identical": report["byte_identical"],
        "reasons": reasons,
    }
    print(json.dumps(payload, sort_keys=True))
    if fail:
        print("FAILED:TST-0330-probe1 python/monitor reducers disagree or corpus is vacuous")
        for row in report["disagreements"][:8]:
            print(json.dumps(row, sort_keys=True)[:500])
        return 1
    print(
        "SUCCESS:TST-0330-probe1 "
        f"corpus={report['corpus_size']} malformed={report['malformed_count']} "
        f"disagreements=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
