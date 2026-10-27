#!/usr/bin/env python3
"""Named probe 2: writeback target verified in the REPO, not only the live tree.

Reviewer stance: re-run the generated regression against both snapshot trees
without trusting the author's classification field. Also plant a live-only
marker and require verify_repo_not_only_live to reject it.
"""

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
    repo_target_path,
    verify_repo_not_only_live,
    writeback,
)

FIXTURES = TOOLS / "selfimprove" / "fixtures"
PRE = FIXTURES / "pre-fix"
POST = FIXTURES / "post-fix"
ESTATE = FIXTURES / "estate"

SKILL_LESSON = {
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

RULE_LESSON = {
    **SKILL_LESSON,
    "lesson_id": "L-empty-id-rule",
    "target_kind": "rule",
    "target_id": "no-empty-id",
}

WORKFLOW_LESSON = {
    **SKILL_LESSON,
    "lesson_id": "L-empty-id-wf",
    "target_kind": "workflow",
    "target_id": "review",
}

TRAP = {
    "lesson_id": "L-trap-live-only",
    "target_kind": "skill",
    "target_id": "id-guard",
    "body": "Planted only in the live tree.",
    "failure_class": "planted",
}


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0374-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0374-p2-") as raw:
        tmp = Path(raw)
        repo = tmp / "repo"
        live = tmp / "live"
        shutil.copytree(ESTATE, repo)
        shutil.copytree(ESTATE, live)

        planted = live / "skills" / "id-guard" / "SKILL.md"
        planted.write_text(
            planted.read_text(encoding="utf-8")
            + "\n<!-- RETAINED-LESSON:L-trap-live-only -->\nplanted live only\n",
            encoding="utf-8",
        )
        trap = verify_repo_not_only_live(repo, live, TRAP)
        if trap["ok"] or not trap["live_only"] or trap["in_repo"]:
            return fail(f"live-only trap was not rejected: {trap}")

        skill_result = writeback(
            repo_root=repo,
            lesson=SKILL_LESSON,
            pre_tree=PRE,
            post_tree=POST,
            live_root=live,
        )
        rule_result = writeback(
            repo_root=repo,
            lesson=RULE_LESSON,
            pre_tree=PRE,
            post_tree=POST,
            live_root=live,
        )
        wf_result = writeback(
            repo_root=repo,
            lesson=WORKFLOW_LESSON,
            pre_tree=PRE,
            post_tree=POST,
            live_root=live,
        )
        for name, row in (
            ("skill", skill_result),
            ("rule", rule_result),
            ("workflow", wf_result),
        ):
            if not row.get("accepted"):
                return fail(f"{name} writeback not accepted: {row}")
            if not row.get("repo_verification", {}).get("ok"):
                return fail(f"{name} repo verification failed: {row}")

        live_skill = (live / "skills" / "id-guard" / "SKILL.md").read_text(encoding="utf-8")
        if "RETAINED-LESSON:L-empty-id" in live_skill:
            return fail("writeback wrote the retained lesson into the live tree")
        if "RETAINED-LESSON:L-trap-live-only" not in live_skill:
            return fail("planted live-only marker disappeared")

        repo_skill = repo_target_path(repo, SKILL_LESSON)
        if "RETAINED-LESSON:L-empty-id" not in repo_skill.read_text(encoding="utf-8"):
            return fail("repo skill missing retained lesson")

        check = verify_repo_not_only_live(repo, live, SKILL_LESSON)
        if not check["ok"] or not check["in_repo"] or check["live_only"]:
            return fail(f"repo verification after writeback failed: {check}")

        # Reviewer: ignore author's accepted field; re-run the generated file.
        generated = Path(skill_result["regression_path"])
        both = evaluate_both_states(generated, PRE, POST)
        if both["pre"]["verdict"] != "RED" or both["post"]["verdict"] != "GREEN":
            return fail(f"reviewer rerun was not RED/GREEN: {both}")
        if not both["accepted"]:
            return fail("reviewer did not accept the protective pair")
        if both["classification"] != "protective":
            return fail(f"reviewer class {both['classification']}")

        wf_path = repo_target_path(repo, WORKFLOW_LESSON)
        doc = json.loads(wf_path.read_text(encoding="utf-8"))
        wf_ids = [row["lesson_id"] for row in doc.get("lessons") or []]
        if "L-empty-id-wf" not in wf_ids:
            return fail(f"workflow lessons {wf_ids}")

        payload = {
            "probe": "probe2-repo-not-only-live",
            "unit_id": "IMP-0374",
            "live_only_trap_rejected": True,
            "skill_in_repo": True,
            "skill_in_live": False,
            "rule_accepted": True,
            "workflow_accepted": True,
            "reviewer_pre": both["pre"]["verdict"],
            "reviewer_post": both["post"]["verdict"],
            "reviewer_classification": both["classification"],
            "pass": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            "live_only_rejected=True repo_has_lesson=True live_lacks_lesson=True "
            "reviewer=RED/GREEN"
        )
        print("SUCCESS:IMP-0374-probe2 repo writeback verified; live-only trap rejected")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
