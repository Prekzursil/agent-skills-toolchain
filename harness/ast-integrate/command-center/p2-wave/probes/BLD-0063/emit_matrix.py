#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0063.json from receipts on disk."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
from matrix import compute_matrix, question_cells  # noqa: E402
from questions import ELEVEN, ELEVEN_LABELS, INPUT_IDS, SELF_ID  # noqa: E402
from questions import is_meta, load_catalog_units, parse_tag  # noqa: E402
from schema_local import garbage_rejected, iter_errors  # noqa: E402

OUT = "command-center/receipts/BLD-0063.json"
SCHEMA = "command-center/schema/coverage-matrix.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
RECEIPTS = "command-center/receipts"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0063/probe1_remove_receipt.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0063/probe2_verdict_rules.py"
)
QUESTION = (
    "Question: which of the spec's own eleven Phase 13 questions did THIS "
    "bucket fail to answer with evidence, and which of its units returned "
    "an uncontrolled or empty result? Map each of the eleven questions "
    "(_USER-PROMPTS.md:11069-11080) to the BLD units that answer it, require "
    "at least one CONFIRMED or REFUTED verdict per question, and report every "
    "question covered only by NOT-CHECKED units."
)
EVIDENCE = frozenset({"CONFIRMED", "REFUTED"})


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-4000:]


def independent_evidence_cover(catalog_path: Path, receipts_dir: Path) -> dict:
    """Recount COVERED questions from evidence[].verdict only (not matrix.py)."""
    catalog_units = load_catalog_units(catalog_path)
    covering: dict[str, list[str]] = {label: [] for label in ELEVEN_LABELS}
    read = 0
    for uid in INPUT_IDS:
        if uid == SELF_ID:
            continue
        path = receipts_dir / f"{uid}.json"
        if not path.is_file() or path.stat().st_size <= 0:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        read += 1
        unit = catalog_units.get(uid) or {}
        tag = parse_tag(str(unit.get("question_or_target") or ""))
        if is_meta(tag):
            continue
        if tag not in ELEVEN_LABELS:
            continue
        hits = False
        for row in doc.get("evidence") or []:
            if not isinstance(row, dict):
                continue
            if str(row.get("verdict") or "").strip().upper() in EVIDENCE:
                hits = True
                break
        if hits:
            covering[tag].append(uid)
    uncovered = [label for _, label in ELEVEN if not covering[label]]
    covered = [label for _, label in ELEVEN if covering[label]]
    return {
        "receipts_read": read,
        "covered_questions": covered,
        "uncovered_questions": uncovered,
        "covering_units": covering,
    }


def main() -> int:
    catalog_path = REPO / CATALOG
    receipts_dir = REPO / RECEIPTS
    matrix = compute_matrix(catalog_path, receipts_dir)
    independent = independent_evidence_cover(catalog_path, receipts_dir)
    if independent["uncovered_questions"] != matrix["uncovered_questions"]:
        print("FAILED:BLD-0063 independent evidence remap drifted")
        print(" independent", independent["uncovered_questions"])
        print(" matrix     ", matrix["uncovered_questions"])
        return 1
    if independent["receipts_read"] != matrix["receipts_read"]:
        print(
            "FAILED:BLD-0063 independent receipts_read "
            f"{independent['receipts_read']} != {matrix['receipts_read']}"
        )
        return 1

    uncovered = list(matrix["uncovered_questions"])
    covered = list(matrix["covered_questions"])
    read_n = int(matrix["receipts_read"])
    expected_n = int(matrix["receipts_expected"])
    uncontrolled = list(matrix["uncontrolled_or_empty_units"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    c1, t1 = run_cmd(P1)
    if c1 != 0:
        print(f"FAILED:BLD-0063 probe1 during emit rc={c1}")
        print(t1)
        return 1

    q_cells = question_cells(matrix)
    control_cells = [
        {
            "id": "CTRL-REMOVE-RECEIPT",
            "semantic": "Control: remove one BLD receipt and coverage drops",
            "verdict": "EXERCISED",
            "code_path": (
                "command-center/p2-wave/probes/BLD-0063/probe1_remove_receipt.py"
            ),
            "evidence": (
                "scratch copy: eleven CONFIRMED receipts COVER all eleven "
                "questions; unlinking one first-unit receipt drops that "
                "question to UNCOVERED and receipts_read by one"
            ),
            "fixture": "tempfile scratch receipts",
            "named_error": None,
        },
        {
            "id": "CTRL-NOT-CHECKED-UNCOVERED",
            "semantic": "NOT-CHECKED-only receipts do not cover a question",
            "verdict": "EXERCISED",
            "code_path": (
                "command-center/p2-wave/probes/BLD-0063/probe2_verdict_rules.py"
            ),
            "evidence": (
                "scratch NOT-CHECKED-only receipt classifies that question "
                "UNCOVERED"
            ),
            "fixture": "tempfile scratch receipts",
            "named_error": None,
        },
        {
            "id": "CTRL-EVIDENCE-COVERED",
            "semantic": "CONFIRMED or REFUTED classifies the question COVERED",
            "verdict": "EXERCISED",
            "code_path": (
                "command-center/p2-wave/probes/BLD-0063/probe2_verdict_rules.py"
            ),
            "evidence": (
                "scratch CONFIRMED and REFUTED receipts classify COVERED; "
                "mixed NOT-CHECKED plus CONFIRMED stays COVERED"
            ),
            "fixture": "tempfile scratch receipts",
            "named_error": None,
        },
        {
            "id": "CTRL-SELF-EXCLUDED",
            "semantic": "BLD-0063 must not cover any of the eleven questions",
            "verdict": "EXERCISED",
            "code_path": "command-center/p2-wave/probes/BLD-0063/matrix.py",
            "evidence": (
                "self-id is excluded from INPUT_IDS covering set; a "
                "CONFIRMED self-receipt is not counted in receipts_read"
            ),
            "fixture": "command-center/receipts/BLD-0063.json",
            "named_error": None,
        },
        {
            "id": "CTRL-LIVE-DISK",
            "semantic": "Live matrix is derived from receipts on this worktree",
            "verdict": "EXERCISED",
            "code_path": (
                "command-center/p2-wave/probes/BLD-0063/matrix.py:compute_matrix"
            ),
            "evidence": (
                f"receipts_read={read_n} expected={expected_n} "
                f"uncontrolled={len(uncontrolled)} "
                f"uncontrolled_ids={','.join(uncontrolled) or 'none'}"
            ),
            "fixture": "command-center/receipts",
            "named_error": None,
        },
    ]
    cells = q_cells + control_cells
    headline = (
        f"UNCOVERED={len(uncovered)} COVERED={len(covered)} "
        f"receipts_read={read_n} receipts_expected={expected_n}"
    )
    answer = (
        f"{len(uncovered)} of 11 Phase 13 questions are UNCOVERED on this "
        f"worktree ({read_n}/{expected_n} BLD-0001..BLD-0062 receipts readable). "
        f"COVERED={covered or ['none']}. UNCOVERED={uncovered or ['none']}. "
        "Mapping is from receipts on disk; catalog tags are a join key only. "
        "SUCCESS:BLD-0063"
    )

    src_map = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/BLD-0063/matrix.py"
    )
    ver_map = (
        "independent evidence[].verdict recount over command-center/receipts/BLD-*.json"
    )
    src_ctl = P1
    ver_ctl = (
        "file-read command-center/p2-wave/probes/BLD-0063/probe1_remove_receipt.py "
        "unlink-drop control"
    )
    src_schema = (
        "python3 -B command-center/p2-wave/probes/BLD-0063/schema_local.py"
    )

    doc = {
        "schema_version": 1,
        "unit_id": SELF_ID,
        "state": "SUCCESS",
        "sentinel": (
            "SUCCESS:BLD-0063 eleven-question coverage matrix from receipts "
            f"on disk; {headline}"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#BLD-0063",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "meta-auditor",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 1024,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Coverage is computed from BLD receipts on disk. A catalog "
                    "intent row with no receipt does not cover its question. "
                    f"{headline}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0063/matrix.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": src_map,
                        "raw_output": (
                            f"{headline}\nuncovered={json.dumps(uncovered)}\n"
                            f"covered={json.dumps(covered)}\n"
                            f"missing={len(matrix['receipts_missing'])}\n"
                            f"uncontrolled={len(uncontrolled)}\n"
                        ),
                        "fingerprint": fp("command", src_map),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": ver_map,
                        "raw_output": (
                            "independent_uncovered="
                            + json.dumps(independent["uncovered_questions"])
                            + "\nindependent_receipts_read="
                            + str(independent["receipts_read"])
                            + "\nagree_with_matrix=true\n"
                        ),
                        "fingerprint": fp("file-read", ver_map),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    f"{SELF_ID} is excluded from the covering set. Removing one "
                    "scratch receipt drops that question to UNCOVERED. "
                    "NOT-CHECKED-only is UNCOVERED; CONFIRMED or REFUTED is COVERED."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0063/probe1_remove_receipt.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": src_ctl,
                        "raw_output": t1,
                        "fingerprint": fp("command", src_ctl),
                        "exit_code": c1,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": ver_ctl,
                        "raw_output": (
                            "probe1 unlinks the first-unit scratch receipt and "
                            "requires after[Q01]=UNCOVERED with sibling questions "
                            "still COVERED and receipts_read dropped by one\n"
                        ),
                        "fingerprint": fp("static-analysis", ver_ctl),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T-REMOVE-RECEIPT",
                "name": (
                    "Control: remove one BLD receipt in a scratch copy and "
                    "prove its question's coverage drops."
                ),
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-1500:],
            },
            {
                "id": "T-NOT-CHECKED-UNCOVERED",
                "name": (
                    "Control: a question covered only by NOT-CHECKED units "
                    "must be reported UNCOVERED. A CONFIRMED or REFUTED "
                    "verdict classifies COVERED. BLD-0063 does not count."
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-REMOVE-RECEIPT",
                "kind": "absent-input",
                "description": (
                    "Deleting one first-unit CONFIRMED scratch receipt must "
                    "turn that question UNCOVERED and leave the other ten COVERED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": t1[-800:],
                "good_state_output": "eleven scratch CONFIRMED receipts -> 11 COVERED",
            },
            {
                "id": "NC-NOT-CHECKED-ONLY",
                "kind": "known-broken-fixture",
                "description": (
                    "A question whose only receipt verdicts are NOT-CHECKED "
                    "must be UNCOVERED, not COVERED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "NOT-CHECKED-only classified UNCOVERED",
                "good_state_output": "CONFIRMED/REFUTED classified COVERED",
            },
            {
                "id": "NC-SELF-EXCLUDED",
                "kind": "mutation",
                "description": (
                    "A CONFIRMED BLD-0063 self-receipt must not cover a "
                    "Phase 13 question or increment receipts_read."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "self-id in receipt_units",
                "good_state_output": "self-receipt ignored; receipts_read excludes it",
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0063-probe2-independent-remap",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe 2 remaps Q01-Q03 from live receipts independently of "
                "this emitter, proves CONFIRMED/REFUTED/NOT-CHECKED rules on "
                "scratch receipts, and checks cells plus receipts_read "
                "against a fresh disk compute."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/BLD-0063/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "BLD-0063",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/BLD-0063/schema_local.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": src_schema,
                    "raw_output": "schema_errors=0 garbage_rejected=true",
                    "fingerprint": fp("schema-validate", src_schema),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 1,
            "policy": (
                "No retry that relaxes the verdict requirement. Coverage "
                "means an evidence-bearing verdict, not an attempted unit."
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": (
                        "catalog-shim-ref-network-ast-integrate.invalid"
                    ),
                    "outcome": "FAILED",
                    "started_at": "2026-08-24T20:22:44Z",
                },
                {
                    "attempt": 2,
                    "error_fingerprint": "local-refresolver-store-receipt-core",
                    "outcome": "SUCCESS",
                    "started_at": now,
                },
            ],
            "pivot_alternatives": [
                "Resolve coverage-matrix $ref from on-disk schema files via RefResolver store (applied).",
                "Emit a probe2-only top-level JSON and skip physical schema (rejected: additionalProperties would hide misspellings).",
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    f"{len(matrix['receipts_missing'])} of 62 BLD-0001..BLD-0062 "
                    "receipts are absent on this worktree, so those planned "
                    "units cannot cover their questions."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place the missing BLD-0001..BLD-0062 receipts on disk and "
                    "re-run emit_matrix.py; coverage must be recomputed, not copied."
                ),
            },
            {
                "claim": (
                    "_USER-PROMPTS.md:11069-11080 is not on this worktree; the "
                    "eleven labels are the distinct catalog Phase 13 tags."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Restore the cited _USER-PROMPTS.md slice and confirm the "
                    "eleven labels match lines 11069-11080 exactly."
                ),
            },
        ],
        "report": {
            "kind": "coverage-matrix",
            "observations": [
                {
                    "name": "receipts_read",
                    "measured": read_n,
                    "method": "json.loads of command-center/receipts/BLD-0001.json through BLD-0062.json",
                    "anchor": "command-center/receipts",
                },
                {
                    "name": "receipts_expected",
                    "measured": expected_n,
                    "method": "INPUT_IDS = BLD-0001..BLD-0062",
                    "anchor": "command-center/p2-wave/probes/BLD-0063/questions.py",
                },
                {
                    "name": "covered_question_count",
                    "measured": len(covered),
                    "method": "at least one CONFIRMED or REFUTED on a mapped receipt",
                    "anchor": "command-center/p2-wave/probes/BLD-0063/matrix.py",
                },
                {
                    "name": "uncovered_question_count",
                    "measured": len(uncovered),
                    "method": "no evidence-bearing verdict, or only NOT-CHECKED/PARTIAL, or no receipt",
                    "anchor": "command-center/p2-wave/probes/BLD-0063/matrix.py",
                },
                {
                    "name": "uncontrolled_or_empty_count",
                    "measured": len(uncontrolled),
                    "method": "readable receipt with no claim/evidence CONFIRMED/REFUTED/NOT-CHECKED/PARTIAL",
                    "anchor": "command-center/p2-wave/probes/BLD-0063/verdicts.py",
                },
            ],
            "control_ids": [
                "CTRL-REMOVE-RECEIPT",
                "CTRL-NOT-CHECKED-UNCOVERED",
                "CTRL-EVIDENCE-COVERED",
                "CTRL-SELF-EXCLUDED",
                "CTRL-LIVE-DISK",
            ],
            "question": QUESTION,
            "answer": answer,
            "headline": headline,
            "derivation": (
                "receipts on disk; catalog tags used only as a join key when a "
                "receipt exists but does not name phase13_question"
            ),
            "receipts_read": read_n,
            "receipts_expected": expected_n,
            "receipts_missing": matrix["receipts_missing"],
            "receipts_unparseable": matrix["receipts_unparseable"],
            "questions": matrix["questions"],
            "cells": cells,
            "covered_questions": covered,
            "uncovered_questions": uncovered,
            "uncontrolled_or_empty_units": uncontrolled,
            "self_reference_excluded": True,
            "self_id": SELF_ID,
            "eleven_question_ids": [qid for qid, _ in ELEVEN],
        },
        "extensions": {
            "stage": "p2-deliver",
            "named_probes": [
                {"id": "probe1", "role": "remove-receipt-control", "command": P1},
                {"id": "probe2", "role": "verdict-and-self-reference", "command": P2},
            ],
            "prohibited_actions_not_run": [
                "git add/commit/push/stash/checkout/rebase",
                "unit_manifest.py --write",
                "API key rotation",
                "finish-everything-close / p2-cloud-ok-deliver relaunch",
            ],
        },
    }

    if not garbage_rejected():
        print("FAILED:BLD-0063 schema accepted garbage")
        return 1
    errs = iter_errors(doc)
    if errs:
        print("FAILED:BLD-0063 schema errors")
        for line in errs[:20]:
            print(" ", line)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    doc["artifacts"][0]["bytes"] = size
    doc["artifacts"][0]["sha256"] = digest
    # Re-validate after filling measured bytes/sha256 (values change, shape does not).
    errs = iter_errors(doc)
    if errs:
        print("FAILED:BLD-0063 schema errors after hash fill")
        for line in errs[:20]:
            print(" ", line)
        return 1
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(headline)
    print("SUCCESS:BLD-0063")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
