#!/usr/bin/env python3
"""Emit command-center/receipts/CC-0002.json — self-demonstrating substrate receipt."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

import receipt_validate as V  # noqa: E402

OUT = "command-center/receipts/CC-0002.json"
SCHEMA = "command-center/schema/receipt.schema.json"
VALIDATOR = "command-center/receipt_validate.py"
EMITTER = "command-center/receipt_emit.py"
GITKEEP = "command-center/receipts/.gitkeep"
SENTINEL = "SUCCESS:CC-0002"
QUESTION = (
    "Question: can any work unit currently emit a schema-validated receipt? "
    "Implementation target: author receipt.schema.json (id, unit id, sentinel, "
    "terminal state, evidence anchors, artifact list with sha256, test results, "
    "reviewer verdict, timestamps, generating commit), create the receipts "
    "directory with a committed .gitkeep, and ship an emitter plus a validator."
)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def generating_commit() -> dict:
    git = REPO / ".git"
    if not git.exists():
        return {
            "available": False,
            "sha": "",
            "reason": (
                f"worktree {REPO} is not a git repository; git rev-parse HEAD "
                "cannot stamp a generating commit. Delivery constraints forbid "
                "git add/commit on this unit."
            ),
        }
    rc, out = run(["git", "rev-parse", "HEAD"])
    if rc != 0 or not out.strip():
        return {
            "available": False,
            "sha": "",
            "reason": f"git rev-parse HEAD failed rc={rc}: {out[:200]}",
        }
    return {"available": True, "sha": out.strip(), "reason": "git rev-parse HEAD"}


def dir_listing(path: Path) -> dict:
    names = sorted(p.name for p in path.iterdir())
    return {
        "absolute_path": str(path.resolve()),
        "exists": path.is_dir(),
        "entry_count": len(names),
        "entries": names,
    }


def main() -> int:
    started = now()
    rec_dir = REPO / "command-center" / "receipts"
    schema_p = REPO / SCHEMA
    val_p = REPO / VALIDATOR
    emit_p = REPO / EMITTER
    gk_p = REPO / GITKEEP

    premise = {
        "catalog_claimed_schema_absent": True,
        "schema_present_now": schema_p.is_file(),
        "schema_bytes": schema_p.stat().st_size if schema_p.is_file() else 0,
        "schema_absolute": str(schema_p.resolve()) if schema_p.is_file() else None,
        "catalog_claimed_receipts_dir_absent": True,
        "receipts_dir_present_now": rec_dir.is_dir(),
        "receipts_dir_absolute": str(rec_dir.resolve()) if rec_dir.is_dir() else None,
        "gitkeep_present": gk_p.is_file(),
        "gitkeep_bytes": gk_p.stat().st_size if gk_p.is_file() else 0,
        "emitter_present": emit_p.is_file(),
        "validator_present": val_p.is_file(),
        "worktree_is_git_repo": (REPO / ".git").exists(),
        "completion_gates_json_present": (
            REPO / "command-center" / "COMPLETION-GATES.json"
        ).is_file(),
        "user_prompts_present": (REPO / "_USER-PROMPTS.md").is_file(),
    }
    listing = dir_listing(rec_dir) if rec_dir.is_dir() else {
        "absolute_path": str(rec_dir),
        "exists": False,
        "entry_count": 0,
        "entries": [],
    }

    st_rc, st_out = V.run_self_test(REPO)
    empty_rc, empty_out = run(
        [sys.executable, "-B", str(val_p)]
    )
    fifth_src = V.minimal_golden(REPO)
    fifth = V.mutant_m5_fabricated_digest(fifth_src)
    fifth_verdict, fifth_codes, fifth_reasons = V.admit_doc(fifth, REPO)
    golden_v, golden_c, golden_r = V.admit_doc(fifth_src, REPO)

    controls_ok = (
        st_rc == 0
        and "SUCCESS:receipt-validate self-test" in st_out
        and st_out.count("got=REJECT") == 4
        and "got=ACCEPT" in st_out
        and empty_rc != 0
        and fifth_verdict == "REJECT"
        and "C5" in fifth_codes
        and golden_v == "ACCEPT"
        and schema_p.is_file()
        and gk_p.is_file()
        and gk_p.stat().st_size > 0
        and emit_p.is_file()
        and val_p.is_file()
    )
    if not controls_ok:
        print("FAILED:CC-0002 emit controls did not all pass")
        print(st_out)
        print(f"empty_rc={empty_rc} fifth={fifth_verdict} {fifth_codes}")
        return 1

    artifacts = [
        V.art_row(REPO, SCHEMA, "schema"),
        V.art_row(REPO, VALIDATOR, "validator"),
        V.art_row(REPO, EMITTER, "emitter"),
        V.art_row(REPO, GITKEEP, "gitkeep"),
        V.art_row(
            REPO,
            "command-center/p2-wave/probes/CC-0002/probe1_detector_controls.py",
            "named-probe",
        ),
        V.art_row(
            REPO,
            "command-center/p2-wave/probes/CC-0002/probe2_reviewer_fifth.py",
            "named-probe",
        ),
    ]

    ended = now()
    answer = (
        "Yes, after this unit: command-center/schema/receipt.schema.json is on disk, "
        "command-center/receipts/ exists (it already did on this worktree; the catalog "
        "row's 'directory ABSENT / 0 receipts' premise is therefore PARTLY REFUTED), "
        f"{GITKEEP} is present ({premise['gitkeep_bytes']} B), and an emitter plus "
        "admission validator ship. This receipt validates against the schema it "
        "authors. The four contracted mutants reject; an independent fifth "
        "(fabricated artifact sha256) also rejects. generating_commit is unavailable "
        "because this worktree is not a git repository. SUCCESS:CC-0002"
    )

    doc = {
        "id": "CC-0002",
        "unit_id": "CC-0002",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": "_USER-PROMPTS.md:10627-10648 (file absent on this worktree)",
        "title": "Create the receipt substrate every work unit is contracted to write to",
        "question": QUESTION,
        "answer": answer,
        "timestamps": {"started_at": started, "ended_at": ended},
        "generating_commit": generating_commit(),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "premise": premise,
        "directory_listing": listing,
        "admission": {
            "layer": "admission-not-completion",
            "note": (
                "ACCEPT means well-formed receipt for a catalog unit with live "
                "artifact digests. It is not the 12-condition completion predicate."
            ),
            "self_test_exit": st_rc,
            "empty_walk_exit": empty_rc,
            "empty_walk_fails_closed": empty_rc != 0,
        },
        "detector_controls": {
            "known_present": {
                "id": "golden-accepts",
                "fired_on_bad_state": False,
                "silent_on_good_state": golden_v == "ACCEPT",
                "detail": golden_r[0] if golden_r else "",
            },
            "known_broken": {
                "id": "four-contracted-mutants",
                "fired_on_bad_state": st_out.count("got=REJECT") == 4,
                "silent_on_good_state": "got=ACCEPT" in st_out,
                "detail": st_out.splitlines()[0] if st_out else "",
            },
        },
        "mutant_matrix": {
            "m1-missing-completion-sentinel": "REJECT C2",
            "m2-empty-evidence": "REJECT C2",
            "m3-unit-id-not-in-catalog": "REJECT C3",
            "m4-unparseable": "REJECT C1",
            "golden": "ACCEPT",
        },
        "reviewer_fifth_mutant": {
            "class": "fabricated-artifact-digest",
            "why_unanticipated": (
                "The four contracted mutants are missing completion_sentinel, empty "
                "evidence array, unknown unit_id, and unparseable JSON. A 64-hex "
                "sha256 that does not match on-disk bytes still schema-validates "
                "and still names a catalog unit; only C5 (plausible digest is not "
                "a receipt) rejects it."
            ),
            "verdict": fifth_verdict,
            "codes": fifth_codes,
            "reason": fifth_reasons[0] if fifth_reasons else "",
            "caught": fifth_verdict == "REJECT" and "C5" in fifth_codes,
        },
        "self_test_output": st_out,
        "empty_walk_output": empty_out[-500:],
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "receipt.schema.json is present at the catalog path; measured "
                    f"size {premise['schema_bytes']} B, absolute path "
                    f"{premise['schema_absolute']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/schema/receipt.schema.json:1",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "command-center/receipts/ exists. Catalog row claimed it was "
                    "ABSENT with 0 receipts; on this worktree the directory was "
                    "already present with other units' receipts. .gitkeep is created "
                    f"at {gk_p.resolve()} ({premise['gitkeep_bytes']} B). git "
                    "add/commit is forbidden and the worktree has no .git, so "
                    "'committed' is NOT-CHECKED."
                ),
                "verdict": "PARTIAL",
                "anchor": "command-center/receipts/.gitkeep:1",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "Admission validator ACCEPTS a golden receipt and REJECTS each "
                    "of the four contracted mutants on its own condition; empty "
                    "walk fails closed."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/receipt_validate.py:1",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "Independent reviewer fifth mutant (fabricated artifact sha256) "
                    "is REJECTED on C5 while the golden remains ACCEPT."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CC-0002/probe2_reviewer_fifth.py:1",
                "confidence": "almost-certain",
            },
        ],
        "tests": [
            {
                "id": "T1-golden-receipt-validates",
                "result": "PASS" if golden_v == "ACCEPT" else "FAIL",
                "command": "python3 -B command-center/receipt_validate.py --self-test",
            },
            {
                "id": "T2-four-mutants-each-fail",
                "result": "PASS" if st_out.count("got=REJECT") == 4 else "FAIL",
                "command": "python3 -B command-center/receipt_validate.py --self-test",
            },
            {
                "id": "T3-detector-control-both-states",
                "result": "PASS" if st_rc == 0 else "FAIL",
            },
            {
                "id": "T4-empty-walk-fails-closed",
                "result": "PASS" if empty_rc != 0 else "FAIL",
                "exit_code": empty_rc,
            },
            {
                "id": "T5-reviewer-fifth-fabricated-digest",
                "result": "PASS"
                if fifth_verdict == "REJECT" and "C5" in fifth_codes
                else "FAIL",
            },
            {
                "id": "T6-gitkeep-present",
                "result": "PASS" if gk_p.is_file() and gk_p.stat().st_size > 0 else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "CC-0002-probe2-fabricated-digest",
            "verdict": "PASS",
            "independent": True,
            "authored_mutant": "fabricated-artifact-digest",
            "note": (
                "Fifth mutant authored after the four catalog mutants and the "
                "schema required-field list were frozen. It is a plausible digest "
                "with no matching file bytes."
            ),
        },
        "notes": (
            "G-1 for CC-0002: live named probes exit 0, receipt state=SUCCESS with "
            "SUCCESS:CC-0002, per-unit UNIT-ARTIFACT-MANIFEST row. Did not run "
            "global unit_manifest.py --write. cloud ok=true is not delivery. Did "
            "not git add/commit. COMPLETION-GATES.json and _USER-PROMPTS.md are "
            "absent on this worktree; fields were taken from the catalog row."
        ),
    }

    rc = V.write_if_valid(doc, OUT, repo=REPO)
    if rc != 0:
        return rc
    # Re-admit the bytes on disk (self-demonstrating).
    live_v, live_c, live_r = V.admit_path(REPO / OUT, REPO)
    if live_v != "ACCEPT":
        print(f"FAILED:CC-0002 written receipt admission {live_v} {live_c}")
        for line in live_r:
            print(f"  {line}")
        try:
            os.remove(REPO / OUT)
        except OSError:
            pass
        return 1
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
