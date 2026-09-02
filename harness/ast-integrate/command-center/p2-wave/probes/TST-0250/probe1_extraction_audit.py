#!/usr/bin/env python3
"""Probe 1: extraction audit on one document + both-states detector."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from extract import QUICKSTART, audit_one_document  # noqa: E402
from harness import run_detector  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0250-probe1 {msg}")
    return 1


def main() -> int:
    audit = audit_one_document(QUICKSTART, "quickstart")
    if audit["extracted_count"] < 1:
        return fail(f"no commands extracted from {audit['path']}")
    if not audit["counts_match"]:
        return fail(
            f"extractor {audit['extracted_count']} != independent fence count "
            f"{audit['independent_fence_count']}"
        )
    if not audit["bodies_present_in_source"]:
        return fail(f"extracted bodies missing from source {audit['missing_bodies']}")

    detector = run_detector()
    if not detector.get("pass"):
        return fail(f"detector {json.dumps(detector, sort_keys=True)}")
    if not detector.get("silent_on_good"):
        return fail("detector was not silent on the good fixture")
    if not detector.get("fired_on_bad"):
        return fail("detector did not fail after a planted broken command")

    payload = {
        "pass": True,
        "probe": "probe1-extraction-audit-and-detector",
        "unit_id": "TST-0250",
        "audit": audit,
        "detector": detector,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:TST-0250-probe1 extraction count matched independent fence "
        "count; detector silent on good and fired on planted broken command"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
