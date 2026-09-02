#!/usr/bin/env python3
"""Probe 2: structural audit of what bypasses the judge.

Mechanically different from probe 1: no corrupt-judge vote experiment.
Reads sdk.py / guard.py, classifies artifact keys as independent vs
judge-mediated, and checks a dual-state detector (silent on execute_spec
majority, fires on aggregate_judge_final).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import mechanism as M  # noqa: E402

ART = REPO / (
    "command-center/adversarial/"
    "ADV-0103-moderator-judge-single-point-failure.json"
)
UNIT = "ADV-0103"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    live = M.measure()
    flags = live["structure"][0]
    independent = set(live["independent_output_ids"])
    payload = {
        "artifact_keys": live["artifact_keys"],
        "decide_mentions_judge": flags["decide_mentions_judge"],
        "execute_calls_guard": flags["execute_calls_guard"],
        "execute_uses_decide": flags["execute_uses_decide"],
        "independent_output_ids": sorted(independent),
        "judge_may_veto": live["judge_may_veto"],
        "recovery_path_raw_records": live["recovery_path_raw_records"],
        "overlay_shipped": live["overlay_judge_final"]["shipped"],
        "sdk_decision_pass_through_judge": next(
            r["pass_through_judge"] for r in live["structure"] if r["output"] == "decision"
        ),
    }
    print(json.dumps(payload, sort_keys=True))

    if not flags["execute_uses_decide"]:
        return fail("execute_spec does not call _decide(votes)")
    if flags["decide_mentions_judge"]:
        return fail("_decide mentions judge; majority is no longer judge-free")
    if flags["execute_calls_guard"]:
        return fail("execute_spec now constructs RoleGuard; re-measure veto wiring")
    if "transcript" not in independent or "votes" not in independent:
        return fail(f"raw records not independent of judge: {sorted(independent)}")
    if not live["recovery_path_raw_records"]:
        return fail("no recovery path: transcript/votes are not independently recorded")
    if not live["judge_may_veto"]:
        return fail("DEFAULT_MANDATES judge.may_veto is not True")
    overlay = next(r for r in live["structure"] if r["output"] == "aggregate_judge_final")
    if not overlay["pass_through_judge"] or overlay["recorded_independently"]:
        return fail("overlay detector did not classify judge-final as judge-mediated")
    decision = next(r for r in live["structure"] if r["output"] == "decision")
    if decision["pass_through_judge"]:
        return fail("shipped decision classified as judge pass-through")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"artifact self-declared {doc.get('state')}")
        rec = (doc.get("measurements") or {}).get("probe2") or {}
        if rec.get("recovery_path_raw_records") != live["recovery_path_raw_records"]:
            return fail("artifact mismatch recovery_path_raw_records")
        if rec.get("execute_calls_guard") != flags["execute_calls_guard"]:
            return fail("artifact mismatch execute_calls_guard")
        if rec.get("decide_mentions_judge") != flags["decide_mentions_judge"]:
            return fail("artifact mismatch decide_mentions_judge")
        nc = next(
            (
                t
                for t in (doc.get("negative_controls") or [])
                if t.get("id") == "NC-JUDGE-FINAL-OVERLAY-FIRES"
            ),
            None,
        )
        if nc is None:
            return fail("negative control NC-JUDGE-FINAL-OVERLAY-FIRES missing")
        if not nc.get("fired_on_bad_state") or not nc.get("silent_on_good_state"):
            return fail("negative control did not discriminate overlay vs shipped majority")
        blob = json.dumps(doc)
        if "transcript" not in blob or "votes" not in blob:
            return fail("artifact does not record independent transcript/votes")
    print("SUCCESS:ADV-0103-probe2 structural bypass and recovery-path audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
