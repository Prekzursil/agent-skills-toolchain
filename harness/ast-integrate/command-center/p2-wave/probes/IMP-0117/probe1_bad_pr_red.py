#!/usr/bin/env python3
"""Probe 1: fixture PR with a bad changed entry makes registry-diff-gate red.

Evidence signal (1): job red on the bad PR.
Evidence signal (2): the job log/report names the CHANGED entry ids, not the
pre-existing dangling entry. A whole-index lint would also name preexisting.bad.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def main() -> int:
    trees = S.trees()
    report = S.gate(trees["base"], trees["bad"])
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"JOB={report['job']}")
    print(f"SCOPE={report['scope']}")
    print("LINTED_ENTRY_IDS=" + ",".join(report["linted_entry_ids"]))
    print("SKIPPED_UNCHANGED_IDS=" + ",".join(report["skipped_unchanged_ids"]))
    print(f"VERDICT={report['verdict']}")
    print(f"FINDING_COUNT={report['finding_count']}")
    print("FINDING_ENTRY_IDS=" + ",".join(report["finding_entry_ids"]))

    if report["verdict"] != "RED":
        print("FAILED:IMP-0117-probe1 expected RED on bad fixture PR")
        return 1
    if report["finding_count"] < 1:
        print("FAILED:IMP-0117-probe1 no findings on bad fixture PR")
        return 1
    if S.PROPOSED_BAD not in report["linted_entry_ids"]:
        print("FAILED:IMP-0117-probe1 changed entry not in LINTED_ENTRY_IDS")
        return 1
    if S.PROPOSED_BAD not in report["finding_entry_ids"]:
        print("FAILED:IMP-0117-probe1 changed entry not in findings")
        return 1
    if S.PREEXISTING_BAD in report["linted_entry_ids"]:
        print("FAILED:IMP-0117-probe1 pre-existing defect was linted (whole-index leak)")
        return 1
    if S.PREEXISTING_BAD in report["finding_entry_ids"]:
        print("FAILED:IMP-0117-probe1 job went red for the unchanged dangling entry")
        return 1
    if report["scope"] != "diff":
        print("FAILED:IMP-0117-probe1 scope is not diff")
        return 1
    if report["job"] != "registry-diff-gate":
        print("FAILED:IMP-0117-probe1 job name mismatch")
        return 1
    rules = {f["rule"] for f in report["findings"]}
    if "secret-gate" not in rules and "digest-mismatch" not in rules:
        print("FAILED:IMP-0117-probe1 expected package or index finding on the changed blob")
        return 1
    print("SUCCESS:IMP-0117-probe1 bad fixture PR red; log names changed entry ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
