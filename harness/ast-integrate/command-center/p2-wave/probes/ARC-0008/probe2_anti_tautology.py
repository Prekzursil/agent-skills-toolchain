#!/usr/bin/env python3
"""Probe 2: anti-tautology, file-path-only rejection, mutation the suite misses.

Anti-tautology: at least one test fails while every declaration file is
syntactically valid (the ignored-loader fixtures).

A mutant that swaps the first test's observable for Path.is_file must be
rejected by the plan checker.

Independent reviewer names and executes M-STALE-PAYLOAD, which survives.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import observables as O  # noqa: E402
import reviewer as R  # noqa: E402
import runtime as RT  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A1/TEST-PLAN.json"


def main() -> int:
    run = S.run_scenario()
    if not run.get("anti_tautology"):
        print("FAILED:ARC-0008-probe2 anti-tautology false")
        return 1
    for label in ("skill_repo_not_live", "hooks_unloaded", "loaded"):
        row = run[label]
        if not row.get("declarations_valid"):
            print(f"FAILED:ARC-0008-probe2 {label} declarations invalid {row.get('declaration_parse_errors')}")
            return 1
    skill_root = HERE / "fixtures" / "skill-repo-not-live"
    ok_json, bad = RT.declaration_files_valid(skill_root)
    print(f"skill_fixture_json_valid={ok_json} bad={bad}")
    if not ok_json:
        print("FAILED:ARC-0008-probe2 skill fixture JSON not valid")
        return 1
    if run["skill_repo_not_live"]["skill_reachable"]:
        print("FAILED:ARC-0008-probe2 reachability passed on ignored skill")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0008-probe2 TEST-PLAN.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = O.check_tests(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0008-probe2 observable/both-states check failed")
        return 1

    mutant = O.file_existence_mutant(doc)
    mok, mwhy = O.check_tests(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0008-probe2 file-existence mutant was accepted")
        return 1

    rev = R.review()
    print(
        json.dumps(
            {
                "reviewer_id": rev.get("reviewer_id"),
                "verdict": rev.get("verdict"),
                "mutation": (rev.get("mutation_suite_would_not_catch") or {}).get("id"),
                "survived": (rev.get("mutation_suite_would_not_catch") or {}).get("survived"),
            },
            sort_keys=True,
        )
    )
    if rev.get("verdict") != "PASS" or not (rev.get("mutation_suite_would_not_catch") or {}).get("survived"):
        print("FAILED:ARC-0008-probe2 reviewer mutation did not survive")
        return 1
    plan_rev = doc.get("reviewer") or {}
    if plan_rev.get("independent") is not True:
        print("FAILED:ARC-0008-probe2 reviewer not independent")
        return 1
    named = (plan_rev.get("mutation_suite_would_not_catch") or {}).get("id")
    if named != "M-STALE-PAYLOAD":
        print(f"FAILED:ARC-0008-probe2 plan reviewer mutation id {named}")
        return 1
    if "SUCCESS:ARC-0008" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0008-probe2 sentinel absent")
        return 1
    print("SUCCESS:ARC-0008-probe2 anti-tautology overclaim mutation-gap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
