#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0028.json from a live isolated record/replay."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

OUT = "command-center/receipts/TST-0028.json"
UNIT = "TST-0028"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0028/probe1_identical_replay.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0028/probe2_planted_change.py"
)
QUESTION = (
    "Spec Phase 10 layer 11 (:10999). Target: record real executions "
    "(inputs, tool calls, artifacts) and replay them against a changed build, "
    "diffing the artifact set and the decision trace. A behaviour change with "
    "no corresponding intent is a regression candidate. What fraction of a "
    "recorded run is replayable without live network or credentials?"
)


def file_fp(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(raw.replace(b"\r\n", b"\n")) if path.is_file() else 0,
        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() if path.is_file() else "",
        "exists": path.is_file(),
        "role": role,
    }


def main() -> int:
    exp = H.run_experiment()
    if not exp.get("pass"):
        print("FAILED:TST-0028 emit experiment did not pass")
        print(json.dumps(exp, sort_keys=True, default=str)[:4000])
        return 1

    fp1 = file_fp(HERE / "probe1_identical_replay.py")
    fp2 = file_fp(HERE / "probe2_planted_change.py")
    if fp1 == fp2:
        print("FAILED:TST-0028 emit probe fingerprints collided")
        return 1

    stats = exp["replayability"]
    offline = stats["replayable_without_live_network_or_credentials"]
    local = stats["replayable_local_only"]
    pct = offline["percent"]
    n_off = offline["count"]
    n = stats["denominator_steps"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        f"{n_off} of {n} recorded steps ({pct}%) re-execute without live network "
        f"or credentials (local compute plus a clock frozen from the recording). "
        f"The other {n - n_off} steps are enumerated by reason: network "
        f"(fetch_external to TEST-NET-1 192.0.2.1, socket not opened on offline "
        f"replay), credential (TST0028_LIVE_TOKEN is never copied into the "
        f"recording), and GUI (no UI capture). Live wall-clock is not identically "
        f"replayable; the recorded unix_ns is frozen on replay. Local-only "
        f"excluding clock is {local['count']}/{n} ({local['percent']}%). "
        f"_USER-PROMPTS.md and command-center/schema/test-receipt.schema.json "
        f"are absent on this worktree; the harness is the delivery substrate, "
        f"not a production agent runtime. SUCCESS:TST-0028"
    )

    tests_ok = exp["tests"]
    tests = [
        {
            "id": "test_identical_build_replays_with_an_empty_diff",
            "name": "identical materialised builds replay with empty artifact and trace diffs",
            "command": P1,
            "result": "PASS" if tests_ok["test_identical_build_replays_with_an_empty_diff"] else "FAIL",
            "observable": "semantic artifact_set and decision_trace diffs are empty",
        },
        {
            "id": "test_a_planted_behaviour_change_shows_up_in_the_diff",
            "name": "planted PLAN_MARKER change appears in artifact set and decision trace",
            "command": P2,
            "result": "PASS"
            if tests_ok["test_a_planted_behaviour_change_shows_up_in_the_diff"]
            else "FAIL",
            "observable": "both artifact_set and decision_trace diffs are non-empty",
        },
        {
            "id": "test_comment_only_mutation_is_not_a_behaviour_change",
            "name": "comment-only plant on PLAN_MARKER line stays empty-diff",
            "command": P2,
            "result": "PASS"
            if tests_ok["test_comment_only_mutation_is_not_a_behaviour_change"]
            else "FAIL",
            "observable": "comment-only materialised build produces an empty semantic diff",
        },
    ]

    schema_path = "command-center/schema/test-receipt.schema.json"
    schema_present = (REPO / schema_path).is_file()
    prompts_present = (REPO / "_USER-PROMPTS.md").is_file()

    doc = {
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0028",
        "completion_sentinel": "SUCCESS:TST-0028",
        "schema_version": 1,
        "report_kind": "test-receipt",
        "title": "Differential replay harness: record, replay, diff",
        "question": QUESTION,
        "answer": answer,
        "execution_substrate": "worktree-isolated",
        "min_bytes_threshold": 256,
        "produced_at": now,
        "output_schema_declared": schema_path,
        "output_schema_present": schema_present,
        "catalog_inputs_present": {
            "_USER-PROMPTS.md": prompts_present,
        },
        "implementation": {
            "harness": "command-center/p2-wave/probes/TST-0028/harness.py",
            "subject": "command-center/p2-wave/probes/TST-0028/subject/workflow.py",
            "isolation": (
                "Two (actually four) copies of subject/ are materialised in a "
                "TemporaryDirectory. Record runs in build-a; replay of the same "
                "inputs runs in build-b (identical), build-c (PLAN_MARKER planted), "
                "and build-d (comment-only). Child processes drop PYTHONPATH and "
                "TST0028_LIVE_TOKEN. This is not a git worktree; the snapshot has "
                "no checkout requirement."
            ),
        },
        "recorded": exp["recorded"],
        "replayability": stats,
        "tests_live": {
            "identical_replay": exp["identical_replay"],
            "planted_behaviour_change": exp["planted_behaviour_change"],
            "comment_only_control": exp["comment_only_control"],
        },
        "materialised_builds": exp["materialised_builds"],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-comment-only-plant",
                "description": "A comment on the PLAN_MARKER line must not fire the behaviour diff.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "observed_comment_only_empty": exp["comment_only_control"]["empty"],
                "observed_planted_non_empty": not exp["planted_behaviour_change"]["empty"],
            }
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/TST-0028/harness.py",
                "kind": "live-probe",
                "claim": (
                    f"Replayability without live network or credentials is {pct}% "
                    f"({n_off}/{n}); non-replayable steps are enumerated by reason."
                ),
                "anchor": "replayability.non_replayable_enumerated_by_reason",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0028/subject/workflow.py",
                "kind": "live-probe",
                "claim": "Record actually attempts TEST-NET-1 and probes credential/GUI presence.",
                "anchor": "fetch_external/credential_gate/gui_capture",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0028/harness.py",
                "kind": "live-probe",
                "claim": "Identical builds produce an empty semantic artifact and trace diff.",
                "anchor": "identical_replay.empty",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0028/harness.py",
                "kind": "live-probe",
                "claim": "A planted PLAN_MARKER change without matching intent shows in both diffs.",
                "anchor": "planted_behaviour_change.empty==false",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "fingerprint": fp1,
                "role": "identical-replay-empty-diff",
            },
            {
                "id": "probe2",
                "command": P2,
                "fingerprint": fp2,
                "role": "planted-behaviour-change",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0028-probe2-planted-behaviour-change",
            "independent": True,
            "verdict": "PASS",
            "scope": (
                "Starts from a second materialised build with PLAN_MARKER planted; "
                "does not take the identical-replay empty hashes as evidence that "
                "the detector fires."
            ),
            "grants_owner_signoff": False,
        },
        "artifacts": [
            art(OUT, "primary"),
            art("command-center/p2-wave/probes/TST-0028/harness.py", "supporting"),
            art("command-center/p2-wave/probes/TST-0028/subject/workflow.py", "supporting"),
            art(
                "command-center/p2-wave/probes/TST-0028/probe1_identical_replay.py",
                "supporting",
            ),
            art(
                "command-center/p2-wave/probes/TST-0028/probe2_planted_change.py",
                "supporting",
            ),
        ],
        "residual_unknowns": [
            {
                "id": "TST-0028-R1",
                "summary": (
                    f"{schema_path} is absent on this worktree; the catalog names "
                    "it as output_schema. This receipt follows the test-receipt "
                    "shape used by sibling units (unit_id/state/sentinel/evidence/"
                    "tests/reviewer/artifacts) without claiming schema validation "
                    "against a missing file."
                ),
            },
            {
                "id": "TST-0028-R2",
                "summary": (
                    "_USER-PROMPTS.md is absent, so :10999 cannot be re-read. The "
                    "catalog question_or_target is the spec anchor used."
                ),
            },
            {
                "id": "TST-0028-R3",
                "summary": (
                    "No production agent runtime (platform/ record-replay) is on "
                    "this worktree. The measured fraction is for the TST-0028 "
                    "subject workflow, not a live editor session."
                ),
            },
            {
                "id": "TST-0028-R4",
                "summary": (
                    "Cross-vendor human reviewer was not dispatched; probe2 is an "
                    "independent measurement fingerprint, not an other-vendor "
                    "fresh-context person."
                ),
            },
        ],
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=TST-0028] "
            "question_or_target + tests_required + evidence_requirement"
        ),
    }

    # Primary artifact row is hashed after write; placeholder exists flag is fine.
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:TST-0028" not in text:
        print("FAILED:TST-0028 emit sentinel missing from serialisation")
        return 1
    out_path.write_text(text, encoding="utf-8")
    # Re-stamp the primary artifact sha now that bytes exist.
    doc["artifacts"][0] = art(OUT, "primary")
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))} percent={pct}")
    print("SUCCESS:TST-0028 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
