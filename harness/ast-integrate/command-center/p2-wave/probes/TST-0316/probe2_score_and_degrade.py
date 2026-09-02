#!/usr/bin/env python3
"""Probe 2: score only the empty-diff subset; mismatch degrades loudly.

Both-states for loud degrade: Codex on a Claude-only Task case returns
UNSUPPORTED (not a FAIL score). A silent-fallback mutant drops Task and
scores 0.0. Portable cases stay READY so the detector is not a constant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.cross_vendor.parity_bench import (  # noqa: E402
    both_states_degrade,
    run_parity,
)

ART = REPO / "command-center/receipts/TST-0316.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0316-probe2 {msg}")
    return 1


def main() -> int:
    honest = run_parity(silent_fallback=False)
    mutant = run_parity(silent_fallback=True)
    ctrl = both_states_degrade()

    empty_ids = {r["case_id"] for r in honest["score_table"]}
    all_ids = {r["case_id"] for r in honest["request_diff_table"]}
    diverged_ids = all_ids - empty_ids
    payload = {
        "probe": "probe2-score-and-degrade",
        "scored_ids": sorted(empty_ids),
        "excluded_ids": sorted(diverged_ids),
        "scores": honest["score_table"],
        "degrade_honest": honest["degrade_rows"],
        "both_states": ctrl,
        "mutant_fail_rows": [
            r
            for r in mutant["degrade_rows"]
            if r.get("scored_as_fail")
        ],
    }
    print(json.dumps(payload, sort_keys=True))

    if not empty_ids:
        return fail("empty-diff subset is empty; refusing a score comparison")
    if "cv-timeout-clamp" in empty_ids:
        return fail("timeout-clamp case leaked into the score table")
    if "cv-claude-task" in empty_ids or "cv-codex-mcp" in empty_ids:
        return fail("capability-mismatch case leaked into the score table")
    for row in honest["score_table"]:
        if row["claude_score"] != row["codex_score"]:
            return fail(
                f"{row['case_id']} scores differ "
                f"{row['claude_score']} vs {row['codex_score']}"
            )
        if row["claude_score"] != 1.0:
            return fail(f"{row['case_id']} portable oracle did not pass")
        if not row["equal"]:
            return fail(f"{row['case_id']} equal flag false")

    by_id = {r["case_id"]: r for r in honest["request_diff_table"]}
    task = by_id["cv-claude-task"]
    if task["codex_status"] != "UNSUPPORTED":
        return fail("Task mismatch scored instead of UNSUPPORTED")
    deg = {r["case_id"]: r for r in honest["degrade_rows"]}
    if deg["cv-claude-task"]["codex_score"] is not None:
        return fail("UNSUPPORTED Codex Task case carried a numeric score")
    if deg["cv-claude-task"]["scored_as_fail"]:
        return fail("honest mismatch was scored as FAIL")
    if deg["cv-codex-mcp"]["claude_status"] != "UNSUPPORTED":
        return fail("Claude did not loudly refuse mcp__codex__codex")
    if deg["cv-codex-mcp"]["claude_score"] is not None:
        return fail("UNSUPPORTED Claude MCP case carried a numeric score")

    if not ctrl["fired_on_bad"]:
        return fail("honest Codex path did not UNSUPPORTED the Task case")
    if not ctrl["mutant_is_fail_score"]:
        return fail("silent-fallback mutant did not score FAIL")
    if not ctrl["silent_on_good"]:
        return fail("portable case was not READY on Codex")
    if not any(r.get("scored_as_fail") for r in mutant["degrade_rows"]):
        return fail("mutant report hid the FAIL score")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:TST-0316" not in text:
            return fail("receipt-sentinel-absent")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"receipt-self-declared {doc.get('state')}")
        if not doc.get("loud_degrade_on_capability_mismatch"):
            return fail("receipt-flag-loud-degrade-absent")
        if not doc.get("scores_restricted_to_empty_request_diff"):
            return fail("receipt-flag-score-subset-absent")

    print(
        "SUCCESS:TST-0316-probe2 "
        f"scored={len(empty_ids)} excluded={len(diverged_ids)} "
        f"loud_degrade={ctrl['fired_on_bad']} mutant_fail={ctrl['mutant_is_fail_score']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
