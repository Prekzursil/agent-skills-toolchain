#!/usr/bin/env python3
"""Probe 1: three negatives + valid control in the SAME invocation.

Also confirms live plugin/marketplace/hook/settings documents survive the
same reader, and that the confirmation artifact recorded that fact.
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
SENTINEL = (
    "SUCCESS:CNF-0035 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all three negative "
    "fixtures errored and the valid control parsed cleanly in the same "
    "invocation. Any other terminal state is FAILED:CNF-0035 "
    "<classification> with the diagnostic tail attached."
)


def main() -> int:
    report = S.run_suite()
    print(
        "same_invocation="
        f"{report['same_invocation']} "
        "negatives_errored="
        f"{report['all_three_negatives_errored']} "
        "control_clean="
        f"{report['control_parsed_clean']} "
        "detector_ok="
        f"{report['detector_ok']} "
        "live_ok="
        f"{report['live_manifests_ok']}"
    )
    for row in report["results"]:
        print(
            f"fixture[{row['id']}] errored={row['errored']} "
            f"classification={row['classification']} ok={row['ok']}"
        )
        if row["error_text"]:
            print(f"  error={row['error_text']}")
    if not report["same_invocation"]:
        print("FAILED:CNF-0035-probe1 not same invocation")
        return 1
    if not report["all_three_negatives_errored"]:
        print("FAILED:CNF-0035-probe1 a negative fixture parsed cleanly")
        return 1
    if not report["control_parsed_clean"]:
        print("FAILED:CNF-0035-probe1 valid control did not parse cleanly")
        return 1
    if not report["detector_ok"]:
        print("FAILED:CNF-0035-probe1 detector classification mismatch")
        return 1
    if not report["live_manifests_ok"]:
        print("FAILED:CNF-0035-probe1 a live manifest/config failed the strict reader")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0035-probe1 confirmation artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:CNF-0035-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text or "SUCCESS:CNF-0035" not in text:
        print("FAILED:CNF-0035-probe1 sentinel absent")
        return 1
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    same = doc.get("same_invocation")
    if same is not True:
        same = report.get("same_invocation")
    if same is not True:
        answers = report.get("answers") if isinstance(report.get("answers"), dict) else {}
        same = answers.get("same_invocation")
    if same is not True:
        print("FAILED:CNF-0035-probe1 artifact same_invocation is not true")
        return 1
    print("SUCCESS:CNF-0035-probe1 same-invocation three-negatives plus control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
