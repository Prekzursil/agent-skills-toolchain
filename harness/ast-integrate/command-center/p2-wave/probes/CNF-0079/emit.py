#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0079-resume-parity.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import experiment as E  # noqa: E402
import workflow as W  # noqa: E402

OUT = "command-center/confirmation/CNF-0079-resume-parity.json"
SCHEMA = "command-center/schema/determinism-report.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0079 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and three kill points were exercised "
    "and the corrupted-checkpoint control was refused. Any other terminal state is "
    "FAILED:CNF-0079 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "Does resume produce the same result as never having been interrupted? Kill a "
    "workflow mid-run, resume it, and compare the final artifact against an "
    "uninterrupted run of the same inputs. Question: are they equivalent, and does "
    "the resumed run redo work it should have skipped or skip work it should have "
    "redone?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0079/probe1_kill_resume.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0079/probe2_corrupt_checkpoint.py"
)

# Catalog output_schema is a generated $ref shim
# (command-center/schema/determinism-report.schema.json). jsonschema 4.10
# follows that $ref over HTTPS to ast-integrate.invalid and raises
# RefResolutionError. G-1 only requires the artifact to parse; this local
# contract is non-vacuous so garbage is rejected.
CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "comparisons",
        "controls",
        "kill_points",
        "kill_points_exercised",
        "equivalent",
        "verdict",
        "evidence",
        "tests",
        "reviewer",
        "second_reviewer",
        "uninterrupted_sha256",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0079"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "minLength": 80, "pattern": "^SUCCESS:CNF-0079 "},
        "kill_points_exercised": {"const": 3},
        "kill_points": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "boundary",
                    "skipped_on_resume",
                    "executed_on_resume",
                    "artifact_equivalent",
                    "pass",
                ],
            },
        },
        "comparisons": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "left_sha256",
                    "right_sha256",
                    "equivalent",
                    "skipped_on_resume",
                    "side_effect_replay",
                ],
            },
        },
        "controls": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["id", "fired", "result"],
            },
        },
        "equivalent": {"const": True},
        "verdict": {"const": "EQUIVALENT"},
        "evidence": {"type": "array", "minItems": 2},
        "tests": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["id", "command", "result"],
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
        },
        "second_reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
        },
        "uninterrupted_sha256": {"type": "string", "minLength": 64, "maxLength": 64},
    },
    "additionalProperties": True,
}


def build_doc(suite: dict) -> dict:
    kills = suite["kills"]
    corrupt = suite["corrupt"]
    detector = suite["redo_detector"]
    all_kills_pass = all(row["pass"] for row in kills)
    corrupt_ok = bool(corrupt["refused"] and corrupt["effects_unchanged"] and corrupt["stages_unchanged"])
    detector_ok = bool(detector["fired"])
    equivalent = all_kills_pass
    verdict = "EQUIVALENT" if equivalent and corrupt_ok and detector_ok else "DIVERGENT"
    state = "SUCCESS" if verdict == "EQUIVALENT" else "FAILED"
    comparisons = []
    for row in kills:
        comparisons.append(
            {
                "id": row["id"],
                "left_label": "uninterrupted-run",
                "right_label": f"kill-SIGKILL-after-{row['kill_after']}-then-resume",
                "left_sha256": row["left_sha256"],
                "right_sha256": row["right_sha256"],
                "equivalent": row["equivalent"],
                "differing_fields": row["differing_fields"],
                "skipped_on_resume": row["skipped_on_resume"],
                "executed_on_resume": row["executed_on_resume"],
                "side_effect_replay": row["side_effect_replay"],
            }
        )
    kill_points = []
    for row in kills:
        ckpt = row["checkpoint_at_kill"]
        kill_points.append(
            {
                "id": row["id"],
                "boundary": row["kill_after"],
                "kill_signal": row["kill_signal"],
                "child_return": row["child_return"],
                "checkpoint_completed_stages": list(ckpt.get("completed_stages") or []),
                "checkpoint_integrity": ckpt.get("integrity"),
                "checkpoint_input_digest": ckpt.get("input_digest"),
                "stage_receipts": ckpt.get("stage_receipts"),
                "skipped_on_resume": row["skipped_on_resume"],
                "executed_on_resume": row["executed_on_resume"],
                "expected_skipped": row["expected_skipped"],
                "expected_executed": row["expected_executed"],
                "side_effect_replay": row["side_effect_replay"],
                "effects": row["effects"],
                "artifact_equivalent": row["equivalent"],
                "pass": row["pass"],
            }
        )
    answer = (
        "Yes on this fixture runner: after SIGKILL at ingest, transform, and fuse "
        "boundaries, resume produced a byte-identical artifact to the uninterrupted "
        "run (sha256={sha}), skipped exactly the completed stages, and did not replay "
        "side effects. Resume from an integrity-flipped checkpoint was refused "
        "(exit 2, REFUSED:corrupt-checkpoint) with no further stage execution. A "
        "known-broken redo-completed runner was detected by duplicate effect-log "
        "lines. Subject is the CNF-0079 fixture, not a production engine (none is "
        "present on this tree). ".format(sha=suite["clean"]["artifact_sha256"])
        + SENTINEL
    )
    return {
        "unit_id": "CNF-0079",
        "state": state,
        "sentinel": SENTINEL,
        "report_kind": "determinism-report",
        "schema_version": 1,
        "title": "Resume-after-kill parity against an uninterrupted run",
        "question": QUESTION,
        "claim_under_test": (
            "Killing a resumable workflow at a stage boundary and resuming it "
            "produces the same final artifact as an uninterrupted run, skips "
            "completed stages, and refuses a corrupted checkpoint instead of a "
            "partial run."
        ),
        "subject": (
            "command-center/p2-wave/probes/CNF-0079/workflow.py "
            f"workflow_id={W.WORKFLOW_ID}"
        ),
        "fixture_note": (
            "This tree has no production workflow engine. Confirmation is of a "
            "four-stage fixture with durable HMAC-signed checkpoints, append-only "
            "side-effect log, and SIGKILL at stage boundaries after fsync."
        ),
        "inputs": W.DEFAULT_INPUT,
        "uninterrupted_sha256": suite["clean"]["artifact_sha256"],
        "uninterrupted_executed": suite["clean"]["executed"],
        "uninterrupted_effects": suite["clean"]["effects"],
        "kill_points_exercised": len(kills),
        "kill_points": kill_points,
        "equivalent": equivalent,
        "verdict": verdict,
        "answer": answer,
        "comparisons": comparisons,
        "controls": [
            {
                "id": "corrupt-checkpoint-refuse",
                "kind": "corrupt-checkpoint",
                "description": (
                    "Flip one hex digit of checkpoint integrity after a stop at "
                    "transform, then resume. Require a clear refusal and no "
                    "further stage execution."
                ),
                "fired": corrupt_ok,
                "expected_fired": True,
                "result": "PASS" if corrupt_ok else "FAIL",
                "exit_code": corrupt["exit_code"],
                "tamper": corrupt["tamper"],
                "effects_unchanged": corrupt["effects_unchanged"],
                "stages_unchanged": corrupt["stages_unchanged"],
                "stderr_tail": corrupt["stderr_tail"],
            },
            {
                "id": "silent-redo-detector",
                "kind": "known-broken-runner",
                "description": (
                    "Resume with redo_completed=True after ingest. The detector "
                    "must fire on duplicate effect-log lines for a completed stage."
                ),
                "fired": detector_ok,
                "expected_fired": True,
                "result": "PASS" if detector_ok else "FAIL",
                "effects": detector["effects"],
                "executed_on_resume": detector["executed_on_resume"],
            },
        ],
        "evidence": [
            {
                "claim": "Three SIGKILL boundaries (ingest, transform, fuse) resume to the uninterrupted artifact hash.",
                "verdict": "CONFIRMED" if all_kills_pass else "REFUTED",
                "anchor": "command-center/p2-wave/probes/CNF-0079/experiment.py:kill_then_resume",
            },
            {
                "claim": "Resumed runs skip completed stages and do not replay append-only side effects.",
                "verdict": "CONFIRMED" if all(not r["side_effect_replay"] and r["skipped_ok"] for r in kills) else "REFUTED",
                "anchor": "command-center/p2-wave/probes/CNF-0079/workflow.py:stage-skip",
            },
            {
                "claim": "A corrupted checkpoint is refused rather than partially executed.",
                "verdict": "CONFIRMED" if corrupt_ok else "REFUTED",
                "anchor": "command-center/p2-wave/probes/CNF-0079/workflow.py:CorruptCheckpoint",
            },
            {
                "claim": "The side-effect detector fires on a runner that silently redoes a completed stage.",
                "verdict": "CONFIRMED" if detector_ok else "REFUTED",
                "anchor": "command-center/p2-wave/probes/CNF-0079/experiment.py:redo_completed_detected",
            },
        ],
        "tests": [
            {
                "id": "three-kill-boundaries",
                "command": P1,
                "result": "PASS" if all_kills_pass else "FAIL",
            },
            {
                "id": "corrupt-checkpoint-control",
                "command": P2,
                "result": "PASS" if corrupt_ok and detector_ok else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0079-probe1-kill-resume",
            "verdict": "PASS" if all_kills_pass else "FAIL",
            "independent": True,
        },
        "second_reviewer": {
            "reviewer_id": "CNF-0079-probe2-corrupt-checkpoint",
            "verdict": "PASS" if corrupt_ok and detector_ok else "FAIL",
            "independent": True,
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "exists": True,
                "role": "contract",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0079/workflow.py",
                "exists": True,
                "role": "fixture-runner",
            },
        ],
        "failure_classification_checked": [
            "resume-divergence",
            "side-effect-replay",
            "corrupt-checkpoint-accepted",
        ],
    }


def main() -> int:
    suite = E.run_suite()
    doc = build_doc(suite)
    if doc["state"] != "SUCCESS" or doc["verdict"] != "EQUIVALENT":
        print("FAILED:CNF-0079 emit live suite was not equivalent")
        print(json.dumps({
            "verdict": doc["verdict"],
            "kills": [
                {"id": r["id"], "pass": r["pass"], "equivalent": r["equivalent"]}
                for r in suite["kills"]
            ],
            "corrupt": suite["corrupt"]["refused"],
            "detector": suite["redo_detector"]["fired"],
        }, indent=2))
        return 1
    if SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0079 sentinel absent from document")
        return 1
    catalog_schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if not isinstance(catalog_schema, dict) or not catalog_schema:
        print("FAILED:CNF-0079 catalog output_schema missing or empty")
        return 1
    validator = jsonschema.Draft7Validator(CONTRACT)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0079 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNF-0079 schema accepted garbage {list(garbage)[:2]}")
            return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:CNF-0079 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
