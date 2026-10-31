#!/usr/bin/env python3
"""Named probe 1: both-states RED then GREEN; tautology REJECTED as non-protective."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from selfimprove.writeback import (  # noqa: E402
    evaluate_both_states,
    writeback,
)

FIXTURES = TOOLS / "selfimprove" / "fixtures"
PRE = FIXTURES / "pre-fix"
POST = FIXTURES / "post-fix"
ESTATE = FIXTURES / "estate"

PROTECTIVE = {
    "lesson_id": "L-empty-id",
    "target_kind": "skill",
    "target_id": "id-guard",
    "body": "Empty identifiers must be rejected at intake.",
    "failure_class": "empty-id-accepted",
    "oracle": {
        "module": "subject",
        "call": "accepts_id",
        "args": [""],
        "expect": False,
    },
}

TAUTOLOGY = {
    "lesson_id": "L-tautology",
    "target_kind": "skill",
    "target_id": "id-guard",
    "body": "A test that passes everywhere protects nothing.",
    "failure_class": "none",
    "regression_kind": "tautology",
}


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0374-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0374-p1-") as raw:
        tmp = Path(raw)
        repo = tmp / "repo"
        shutil.copytree(ESTATE, repo)
        protective = writeback(
            repo_root=repo,
            lesson=PROTECTIVE,
            pre_tree=PRE,
            post_tree=POST,
        )
        tautology = writeback(
            repo_root=repo,
            lesson=TAUTOLOGY,
            pre_tree=PRE,
            post_tree=POST,
        )
        if not protective.get("accepted"):
            return fail(f"protective lesson not accepted: {protective}")
        if protective.get("pre_verdict") != "RED" or protective.get("post_verdict") != "GREEN":
            return fail(f"protective pair not RED/GREEN: {protective}")
        if "CASE empty-id-accepted" not in (protective.get("pre_stdout") or ""):
            return fail("pre-fix RED run did not print the failure CASE line")
        if "SUMMARY failed=0" not in (protective.get("post_stdout") or ""):
            return fail("post-fix GREEN run missing SUMMARY failed=0")

        test_file = Path(protective["regression_path"])
        both = evaluate_both_states(test_file, PRE, POST)
        if both["pre"]["verdict"] != "RED" or both["post"]["verdict"] != "GREEN":
            return fail(f"independent rerun mismatch: {both}")
        if not both["accepted"]:
            return fail("independent rerun did not accept RED/GREEN")

        if tautology.get("accepted"):
            return fail("tautology was wrongly accepted")
        if tautology.get("classification") != "non_protective":
            return fail(f"tautology class {tautology.get('classification')}")
        if tautology.get("pre_verdict") != "GREEN" or tautology.get("post_verdict") != "GREEN":
            return fail(f"tautology was not GREEN/GREEN: {tautology}")
        if tautology.get("wrote_lesson"):
            return fail("tautology wrote a retained lesson")
        skill = (repo / "skills" / "id-guard" / "SKILL.md").read_text(encoding="utf-8")
        if "RETAINED-LESSON:L-tautology" in skill:
            return fail("tautology marker present in skill")
        if not (repo / "selfimprove" / "rejected" / "L-tautology.json").is_file():
            return fail("rejected record missing for tautology")
        if (repo / "selfimprove" / "retained" / "L-tautology.json").is_file():
            return fail("tautology retained")
        if "RETAINED-LESSON:L-empty-id" not in skill:
            return fail("protective marker missing from repo skill")

        payload = {
            "probe": "probe1-both-states",
            "unit_id": "IMP-0374",
            "protective_pre": protective["pre_verdict"],
            "protective_post": protective["post_verdict"],
            "protective_accepted": True,
            "independent_pre": both["pre"]["verdict"],
            "independent_post": both["post"]["verdict"],
            "tautology_pre": tautology["pre_verdict"],
            "tautology_post": tautology["post_verdict"],
            "tautology_rejected": True,
            "tautology_classification": tautology["classification"],
            "pass": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            "pre=RED post=GREEN tautology_rejected=True "
            "independent_rerun=RED/GREEN"
        )
        print("SUCCESS:IMP-0374-probe1 both-states RED then GREEN; tautology rejected")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
