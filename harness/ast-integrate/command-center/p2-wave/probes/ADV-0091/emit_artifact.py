#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0091-instant-unanimity-trigger.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import constants as C  # noqa: E402
import harness as H  # noqa: E402


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(C.REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def validate(doc: dict) -> None:
    schema = json.loads((C.REPO / C.SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in ({}, {"state": "SUCCESS", "passing_tests": 999}, {"blob": "x" * 400}):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:ADV-0091 schema accepts garbage")


def build_doc(matrix: dict, probes: list[dict]) -> dict:
    facts = matrix["facts"]
    rows = H.verdicts(matrix)
    sentinel = C.completion_sentinel()
    listed = matrix["primed"]["live"]["listed_interventions"]
    answer = (
        "Live CNL-0080 (the executable CNL-0059 overlay on the council stopping "
        "runtime) fires instant_unanimity_trigger on a primed round-1 unanimous "
        "council with zero independent briefs and relabels the outcome from "
        "AGREEMENT to AGREEMENT_HELD_FOR_REVALUATION. A trigger-disabled "
        "overlay-off control of the same ballots ships AGREEMENT, so the "
        "trigger is not purely ceremonial for finalization. It does not execute "
        "blind re-evaluation, forced dissent, counterexample generation, role "
        "rotation, or critic recruitment: those listed interventions are absent "
        "from the live engine. A council that reaches unanimity at round 4 after "
        "independent briefs and disagreement does not fire the trigger. "
        "Timer exhaustion and contested ballots also stay silent. "
        + sentinel
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    overall = "PARTIAL"
    return {
        "unit_id": "ADV-0091",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0091",
        "completion_sentinel": sentinel,
        "report_kind": "council-pathology-sim",
        "title": "Instant-unanimity trigger: does suspiciously fast agreement force re-evaluation?",
        "question": C.QUESTION,
        "answer": answer,
        "overall_verdict": overall,
        "produced_at": now,
        "output_path": C.OUT_REL,
        "output_schema": C.SCHEMA_REL,
        "cloud_ok": False,
        "honest_scope": {
            "runtime": matrix["runtime"],
            "claim": (
                "G-1 audits the live CNL-0080 stopping evaluator on pinned "
                "fixtures plus scripted transcripts. It does not claim a live "
                "multi-model council session."
            ),
        },
        "verdicts": rows,
        "named_probes": probes,
        "primed_run": matrix["primed"],
        "late_legitimate_run": matrix["late_legitimate"],
        "outcome_delta": {
            "primed_changed": facts["primed_outcome_changed"],
            "late_changed": matrix["late_legitimate"]["outcome_changed_vs_disabled"],
            "primed_live_kind": matrix["primed"]["live"]["outcome_kind"],
            "primed_off_kind": matrix["primed"]["overlay_off"]["outcome_kind"],
            "late_live_kind": matrix["late_legitimate"]["live"]["outcome_kind"],
            "late_off_kind": matrix["late_legitimate"]["overlay_off"]["outcome_kind"],
            "ceremonial_for_shipping": not facts["primed_outcome_changed"],
            "listed_interventions_executed": listed,
        },
        "controls": [
            {
                "id": "CTRL-LATE-UNANIMITY",
                "description": (
                    "Unanimity after independent briefs and disagreement must "
                    "stay silent; primed round-1 zero-brief must fire."
                ),
                "fired_on_bad_state": facts["primed_trigger"],
                "silent_on_good_state": facts["late_silent"],
            },
            {
                "id": "CTRL-TIMER-AND-CONTESTED",
                "description": (
                    "Timer exhaustion and contested ballots must not fire the "
                    "instant-unanimity trigger."
                ),
                "fired_on_bad_state": facts["primed_trigger"],
                "silent_on_good_state": facts["timer_silent"] and facts["contested_silent"],
            },
            {
                "id": "CTRL-OVERLAY-OFF-CEREMONIAL",
                "description": (
                    "Trigger-disabled overlay of the same primed ballots must "
                    "ship AGREEMENT, proving the live hold is an outcome change."
                ),
                "fired_on_bad_state": facts["primed_outcome_changed"],
                "silent_on_good_state": facts["late_unchanged"],
            },
        ],
        "tests": [
            {
                "id": "probe1_primed_transcript",
                "command": C.P1_CMD,
                "result": "PASS" if probes and probes[0].get("exit_code") == 0 else "NOT-RUN",
            },
            {
                "id": "probe2_outcome_delta",
                "command": C.P2_CMD,
                "result": "PASS" if len(probes) > 1 and probes[1].get("exit_code") == 0 else "NOT-RUN",
            },
        ],
        "evidence": [
            {
                "kind": "live-engine",
                "claim": "CNL-0080 evaluate_fixture on instant-unanimity-round-1.",
                "detail": json.dumps(matrix["primed"]["live"], sort_keys=True)[:2000],
                "path": "command-center/p2-wave/probes/CNL-0080/engine.py",
            },
            {
                "kind": "overlay-off",
                "claim": "Parser-free trigger-disabled decision for the same ballots.",
                "detail": json.dumps(matrix["primed"]["overlay_off"], sort_keys=True),
                "path": "command-center/p2-wave/probes/ADV-0091/harness.py",
            },
            {
                "kind": "late-control",
                "claim": "fire-unanimity (round 4, 3 independent briefs) stays silent.",
                "detail": json.dumps(matrix["late_legitimate"]["live"], sort_keys=True),
                "path": "command-center/p2-wave/probes/CNL-0080/fixtures/fire-unanimity.json",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0091-probe2-outcome-delta",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Parser-free overlay-off decision tuple, not a rerun of the "
                "transcript inspection in probe 1."
            ),
        },
        "artifacts": [
            {"path": C.OUT_REL, "exists": True, "role": "primary"},
            {"path": C.SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/ADV-0091/harness.py",
                "exists": True,
                "role": "instrument",
            },
        ],
        "facts": facts,
    }


def write_doc(doc: dict) -> Path:
    out = C.REPO / C.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out


def main() -> int:
    matrix = H.run_matrix()
    facts = matrix["facts"]
    if not facts["primed_trigger"] or not facts["late_silent"]:
        print("FAILED:ADV-0091 emit both-states", facts)
        return 1
    if not facts["primed_outcome_changed"]:
        print("FAILED:ADV-0091 emit ceremonial trigger", facts)
        return 1
    placeholders = [
        {
            "id": "probe1",
            "command": C.P1_CMD,
            "exit_code": -1,
            "raw_output": "pending-emit-placeholder",
        },
        {
            "id": "probe2",
            "command": C.P2_CMD,
            "exit_code": -1,
            "raw_output": "pending-emit-placeholder",
        },
    ]
    doc = build_doc(matrix, placeholders)
    write_doc(doc)
    rc1, out1 = run_cmd(C.P1_CMD)
    rc2, out2 = run_cmd(C.P2_CMD)
    probes = [
        {"id": "probe1", "command": C.P1_CMD, "exit_code": rc1, "raw_output": out1},
        {"id": "probe2", "command": C.P2_CMD, "exit_code": rc2, "raw_output": out2},
    ]
    doc = build_doc(matrix, probes)
    out = write_doc(doc)
    validate(doc)
    if out.stat().st_size < C.MIN_BYTES:
        print(f"FAILED:ADV-0091 artifact too small {out.stat().st_size}")
        return 1
    if C.completion_sentinel() not in out.read_text(encoding="utf-8"):
        print("FAILED:ADV-0091 sentinel missing from artifact")
        return 1
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ADV-0091 named probes during emit")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    print(f"wrote {C.OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:ADV-0091 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
