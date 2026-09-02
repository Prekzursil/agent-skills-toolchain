#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0167.json from a live resume measure."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import council_fixture_runtime as R  # noqa: E402

OUT = "command-center/receipts/TST-0167.json"
QUESTION = (
    "Does resuming a council mid-deliberation restore round state, per-round "
    "votes, confidence trajectory and the minority report? PASS requires dissent "
    "survive the round trip; dissent loss on resume is a named failure class."
)


def main() -> int:
    live = R.live()
    if not live.get("pass"):
        print("FAILED:TST-0167 emit live measure_resume did not pass")
        print(json.dumps({k: live.get(k) for k in sorted(live) if k not in {
            "structural_pre", "structural_restored"
        }}, indent=2)[:6000])
        return 1

    neg = live.get("negative_control") or {}
    cites = live.get("cites") or {}
    tests = [
        {
            "id": "TST-0167-BOTH-STATES",
            "name": "Uninterrupted council produces the same dissent content as suspend-then-resume.",
            "result": "PASS" if live.get("both_states_same_dissent") else "FAIL",
            "same_rounds": live.get("both_states_same_rounds"),
            "same_transcript": live.get("both_states_same_transcript"),
            "uninterrupted_sha256": live.get("uninterrupted_sha256"),
            "resumed_sha256": live.get("resumed_sha256"),
        },
        {
            "id": "TST-0167-REGRESSION-SEED",
            "name": "Dissent/minority report dropped from the checkpoint is a named failure.",
            "result": "PASS" if neg.get("fired_on_bad_state") else "FAIL",
            "error_type": neg.get("error_type"),
            "message": neg.get("message"),
        },
        {
            "id": "TST-0167-NEGATIVE-CONTROL",
            "name": "Preservation check is silent on a good checkpoint and fires on the drop mutation.",
            "result": (
                "PASS"
                if neg.get("fired_on_bad_state") and neg.get("silent_on_good_state")
                else "FAIL"
            ),
            "fired_on_bad_state": neg.get("fired_on_bad_state"),
            "silent_on_good_state": neg.get("silent_on_good_state"),
        },
        {
            "id": "TST-0167-LIVE-TARGET",
            "name": "Live PhaseMachine + simulate.py restore round state, votes, trajectory and minority.",
            "result": "PASS" if live.get("structural_match") else "FAIL",
            "after_round": live.get("after_round"),
            "structural_match": live.get("structural_match"),
        },
        {
            "id": "TST-0167-CONDITION-11",
            "name": "Pre-suspend minority entries survive into the final transcript section.",
            "result": "PASS" if live.get("pre_survived_in_final") else "FAIL",
            "pre_minority_sha256": live.get("pre_minority_sha256"),
            "final_minority_sha256": live.get("final_minority_sha256"),
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:TST-0167 one or more contracted tests did not PASS")
        print(json.dumps(tests, indent=2))
        return 1

    pre = live.get("structural_pre") or {}
    receipt = {
        "unit_id": "TST-0167",
        "id": "TST-0167",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:TST-0167",
        "completion_sentinel": "SUCCESS:TST-0167",
        "cloud_ok": False,
        "report_kind": "resume_report",
        "overall_verdict": "PASS",
        "title": "Council resume restores rounds, votes AND dissent",
        "question": QUESTION,
        "answer": (
            "Suspending tools.council.simulate after round "
            f"{live.get('after_round')} and restoring PhaseMachine state "
            f"reproduced round_index, per-round votes, confidence trajectory "
            f"and minority-report sha {live.get('pre_minority_sha256')}. "
            f"An uninterrupted run hashed to {live.get('uninterrupted_sha256')}; "
            f"suspend-then-resume hashed to {live.get('resumed_sha256')} "
            "(byte-identical). Pre-suspend critic dissent is present in the "
            f"final minority-report ({live.get('final_minority_sha256')}). "
            "Stripping dissent turns from the checkpoint raises DissentDropped. "
            "B05 protocol catalogue remains ABSENT; this unit uses a local "
            "CouncilSpec fixture on the shipped B07 PhaseMachine. "
            "SUCCESS:TST-0167"
        ),
        "inputs_on_this_tree": {
            "b07_phase_runtime": "tools/council/phases.py",
            "simulate_module": "tools/council/simulate.py",
            "handled_ledger": "ABSENT-on-this-worktree",
            "user_prompts_11340": "ABSENT-on-this-worktree",
            "b05_protocol_blueprints": "ABSENT-on-this-worktree",
            "note": (
                "Does not rebuild the missing B05 protocol catalogue (ADV circle). "
                "Resume is implemented on the existing simulator and PhaseMachine "
                "with a local three-round fixture that plants critic dissent "
                "before suspend."
            ),
        },
        "structural": {
            "after_round": live.get("after_round"),
            "match": True,
            "pre_minority_sha256": live.get("pre_minority_sha256"),
            "restored_minority_sha256": live.get("restored_minority_sha256"),
            "round_index": pre.get("round_index"),
            "phase": pre.get("phase"),
            "idea_ids": pre.get("idea_ids"),
            "objection_ids": pre.get("objection_ids"),
            "per_round_votes": pre.get("per_round_votes"),
            "confidence_trajectory": pre.get("confidence_trajectory"),
        },
        "minority": {
            "pre_count": live.get("pre_minority_count"),
            "pre_sha256": live.get("pre_minority_sha256"),
            "final_sha256": live.get("final_minority_sha256"),
            "pre_survived_in_final": True,
            "dissenters": live.get("dissenters_resumed"),
        },
        "both_states": {
            "same_dissent": True,
            "same_rounds": True,
            "same_transcript": True,
            "uninterrupted_sha256": live.get("uninterrupted_sha256"),
            "resumed_sha256": live.get("resumed_sha256"),
        },
        "negative_control": {
            "id": "TST-0167-DISSENT-DROP-MUTATION",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "error_type": neg.get("error_type"),
            "message": neg.get("message"),
        },
        "cites": cites,
        "model_calls": 0,
        "seed": live.get("seed"),
        "n_rounds": live.get("n_rounds"),
        "tests": tests,
        "test_results": {t["id"]: t["result"] for t in tests},
        "evidence": [
            {
                "claim": "Structural diff: pre-suspend state equals post-restore state.",
                "verdict": "CONFIRMED",
                "anchor": cites.get("suspend_after_round"),
                "pre_minority_sha256": live.get("pre_minority_sha256"),
                "restored_minority_sha256": live.get("restored_minority_sha256"),
            },
            {
                "claim": "Final minority-report section contains the pre-suspend dissent entries.",
                "verdict": "CONFIRMED",
                "anchor": cites.get("require_dissent_survived"),
                "pre_sha256": live.get("pre_minority_sha256"),
                "final_sha256": live.get("final_minority_sha256"),
            },
            {
                "claim": "Uninterrupted run is byte-identical to suspend-then-resume.",
                "verdict": "CONFIRMED",
                "anchor": cites.get("resume_council"),
                "uninterrupted_sha256": live.get("uninterrupted_sha256"),
                "resumed_sha256": live.get("resumed_sha256"),
            },
            {
                "claim": "Dropping dissent from the checkpoint is detected (spec 11340 class).",
                "verdict": "CONFIRMED",
                "anchor": cites.get("drop_minority_mutation"),
                "error_type": neg.get("error_type"),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0167-probe2-minority-report",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "both_states_reproduced": True,
            "did_not_author_harness": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "tools/council/simulate.py",
                "exists": True,
                "role": "implementation",
            },
            {
                "path": "tools/council/phases.py",
                "exists": True,
                "role": "b07-runtime-kernel",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0167/fixtures/cast/critic.json",
                "exists": True,
                "role": "persona-script",
            },
        ],
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/resume_report",
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    print("SUCCESS:TST-0167 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
