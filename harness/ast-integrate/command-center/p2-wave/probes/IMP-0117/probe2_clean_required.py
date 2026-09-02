#!/usr/bin/env python3
"""Probe 2: BOTH-STATES green on a clean fixture PR + required-context review.

The same configuration that went red on the bad PR must go green on a clean
proposed entry even though the base index still carries preexisting.bad.
A whole-index control on that clean head is red — proving the CI job is
diff-scoped, not a weaker full-index lint.

Reviewer requirement: the job is listed as a required status check. A
non-required red job blocks nothing; the merge policy is tested both ways.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))
import scenario as S  # noqa: E402
from tools.marketplace.required_contexts import (  # noqa: E402
    job_is_required,
    merge_decision,
    required_contexts,
)

WORKFLOWS = (
    REPO / ".github/workflows/registry-diff-gate.yml",
    REPO / "ci/workflows/registry-diff-gate.yml",
)


def main() -> int:
    trees = S.trees()
    clean = S.gate(trees["base"], trees["clean"])
    print(f"clean_verdict={clean['verdict']}")
    print("clean_LINTED_ENTRY_IDS=" + ",".join(clean["linted_entry_ids"]))
    print("clean_SKIPPED_UNCHANGED_IDS=" + ",".join(clean["skipped_unchanged_ids"]))
    print(f"clean_finding_count={clean['finding_count']}")

    if clean["verdict"] != "GREEN":
        print("FAILED:IMP-0117-probe2 clean fixture PR was not green")
        return 1
    if clean["finding_count"] != 0:
        print("FAILED:IMP-0117-probe2 clean PR has findings")
        return 1
    if clean["linted_entry_ids"] != [S.PROPOSED_CLEAN]:
        print("FAILED:IMP-0117-probe2 clean PR did not lint only the proposed entry")
        return 1
    if S.PREEXISTING_BAD not in clean["skipped_unchanged_ids"]:
        print("FAILED:IMP-0117-probe2 pre-existing bad entry was not skipped")
        return 1

    whole = S.whole(trees["clean"])
    print(f"whole_index_verdict={whole['verdict']}")
    print("whole_FINDING_ENTRY_IDS=" + ",".join(whole["finding_entry_ids"]))
    if whole["verdict"] != "RED":
        print("FAILED:IMP-0117-probe2 whole-index control should be red on the same clean head")
        return 1
    if S.PREEXISTING_BAD not in whole["finding_entry_ids"]:
        print("FAILED:IMP-0117-probe2 whole-index control missed preexisting.bad")
        return 1

    req = required_contexts(REPO)
    print("required_contexts=" + ",".join(req))
    if not job_is_required(REPO, "registry-diff-gate"):
        print("FAILED:IMP-0117-probe2 registry-diff-gate is not a required context")
        return 1

    red_statuses = {"registry-diff-gate": "failure"}
    required_blocks = merge_decision(req, red_statuses)
    print(f"required_red_blocks_merge={not required_blocks['allowed']}")
    if required_blocks["allowed"]:
        print("FAILED:IMP-0117-probe2 required red job did not block merge")
        return 1
    non_required = merge_decision([], red_statuses)
    print(f"non_required_red_blocks_nothing={non_required['allowed']}")
    if not non_required["allowed"]:
        print("FAILED:IMP-0117-probe2 empty required list still blocked — mutant inverted")
        return 1

    job_re = re.compile(r"^  registry-diff-gate:\s*$", re.M)
    for path in WORKFLOWS:
        if not path.is_file():
            print(f"FAILED:IMP-0117-probe2 missing workflow {path}")
            return 1
        text = path.read_text(encoding="utf-8")
        if not job_re.search(text) or "name: registry-diff-gate" not in text:
            print(f"FAILED:IMP-0117-probe2 job name missing in {path}")
            return 1
        print(f"workflow_ok={path.relative_to(REPO).as_posix()}")

    print("SUCCESS:IMP-0117-probe2 clean PR green; whole-index control red; required context")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
