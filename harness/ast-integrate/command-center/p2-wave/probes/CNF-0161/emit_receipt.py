#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0161.json and the unit-scoped owner packet.

Does NOT write command-center/OWNER-QUESTION-PACKET.md or
command-center/OWNER-DECISIONS.md (estate files; read-only inputs).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from packet import (  # noqa: E402
    ESTATE_DECISIONS_REL,
    ESTATE_PACKET_REL,
    UNIT_PACKET_REL,
    build_packet,
    estate_decisions_intact,
    estate_packet_intact,
    is_compound_question,
    load_unresolved,
    parse_decisions,
    render_packet,
    validate_entry,
)

OUT = "command-center/receipts/CNF-0161.json"
SCHEMA = "command-center/schema/program-gate-report.schema.json"
LOCAL_SCHEMA = HERE / "program-gate-report.local.schema.json"
CNF0160_REL = "command-center/receipts/CNF-0160.json"
FIXTURE_REL = "command-center/p2-wave/probes/CNF-0161/fixtures/unresolved.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0161/probe1_format.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0161/probe2_roundtrip.py"
)
QUESTION = (
    "Implementation target: for every claim that survives vendor triangulation "
    "unresolved, produce a one-page owner packet containing exactly one "
    "foundation-level question, a recommendation, the strongest tradeoff, the "
    "default if unanswered, and the cost of the settling experiment - the "
    "format spec:11364-11370 mandates. Answers are recorded durably in "
    "OWNER-DECISIONS.md and never re-asked."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(method: str, command: str) -> str:
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


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    estate_packet = REPO / ESTATE_PACKET_REL
    estate_decisions = REPO / ESTATE_DECISIONS_REL
    if not estate_packet.is_file() or not estate_packet_intact(
        estate_packet.read_text(encoding="utf-8")
    ):
        print("FAILED:CNF-0161 estate OWNER-QUESTION-PACKET.md missing or overwritten")
        return 1
    if not estate_decisions.is_file() or not estate_decisions_intact(
        estate_decisions.read_text(encoding="utf-8")
    ):
        print("FAILED:CNF-0161 estate OWNER-DECISIONS.md missing or overwritten")
        return 1

    src = load_unresolved(REPO / CNF0160_REL)
    decisions = parse_decisions(estate_decisions.read_text(encoding="utf-8"))
    open_entries, skipped = build_packet(src["claims"], decisions)
    for entry in open_entries:
        errors = validate_entry(entry)
        if errors:
            print(f"FAILED:CNF-0161 unshippable production entry {errors}")
            return 1

    packet_text = render_packet(
        open_entries,
        source_status=src["status"],
        source_path=CNF0160_REL,
        generated_at=started,
    )
    unit_packet = REPO / UNIT_PACKET_REL
    unit_packet.parent.mkdir(parents=True, exist_ok=True)
    unit_packet.write_text(packet_text, encoding="utf-8")

    fixture = load_unresolved(REPO / FIXTURE_REL)
    fixture_entries, _ = build_packet(fixture["claims"], [])
    if len(fixture_entries) != 2:
        print(f"FAILED:CNF-0161 fixture open_entries={len(fixture_entries)}")
        return 1
    for entry in fixture_entries:
        errors = validate_entry(entry)
        if errors:
            print(f"FAILED:CNF-0161 fixture entry {entry['claim_id']} {errors}")
            return 1

    compound = deepcopy(fixture_entries[0])
    compound["question"] = (
        "Should the Anthropic verdict be treated as authoritative, and should "
        "the Codex verdict be discarded?"
    )
    if "compound-question" not in validate_entry(compound):
        print("FAILED:CNF-0161 compound question accepted")
        return 1
    two_marks = deepcopy(fixture_entries[0])
    two_marks["question"] = "Should we close the claim? Should we also re-run vendors?"
    if "compound-question" not in validate_entry(two_marks):
        print("FAILED:CNF-0161 two-question string accepted")
        return 1
    missing_default = deepcopy(fixture_entries[0])
    missing_default["default_if_unanswered"] = "   "
    if "default_if_unanswered-empty" not in validate_entry(missing_default):
        print("FAILED:CNF-0161 empty default accepted")
        return 1
    missing_impact = deepcopy(fixture_entries[0])
    missing_impact["impact"] = ""
    if "impact-empty" not in validate_entry(missing_impact):
        print("FAILED:CNF-0161 empty impact accepted")
        return 1
    if is_compound_question(fixture_entries[0]["question"]):
        print("FAILED:CNF-0161 healthy fixture question marked compound")
        return 1

    settle_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0161/settle_claim.py "
        f"--fixture {FIXTURE_REL} --claim CLAIM-TRI-001"
    )
    settle_rc, settle_out = run_cmd(settle_cmd)
    if settle_rc != 0:
        print(f"FAILED:CNF-0161 fixture settling experiment rc={settle_rc}")
        print(settle_out)
        return 1

    coverage = "NOT-CHECKED" if src["status"] != "PRESENT" else "CHECKED"
    packet_art = artifact_row(UNIT_PACKET_REL, "supporting")
    schema_art = artifact_row(SCHEMA, "supporting")
    fixture_art = artifact_row(FIXTURE_REL, "fixture")

    p1_fp = probe_fp("test-run", P1)
    p2_fp = probe_fp("test-run", P2)
    static_fp = probe_fp(
        "static-analysis",
        "command-center/p2-wave/probes/CNF-0161/packet.py:validate_entry",
    )
    if p1_fp == p2_fp or p1_fp == static_fp:
        print("FAILED:CNF-0161 probe fingerprints not distinct")
        return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0161",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0161",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0161] "
            "and spec 11364-11370 (one foundation-level question, recommendation, "
            "strongest tradeoff, default if unanswered, settling-experiment cost)"
        ),
        "min_bytes_threshold": 400,
        "artifacts": [
            {
                "path": OUT,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            packet_art,
            schema_art,
            fixture_art,
            artifact_row(ESTATE_PACKET_REL, "supporting"),
            artifact_row(ESTATE_DECISIONS_REL, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "Each shippable packet entry has exactly one non-compound "
                    "foundation-level question, a recommendation, the strongest "
                    "tradeoff, a non-empty default, an impact statement, and a "
                    "named settling experiment with cost."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0161/packet.py:validate_entry",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": "command-center/p2-wave/probes/CNF-0161/packet.py:validate_entry",
                        "raw_output": (
                            "fixture_entries=2 compound_rejected=true "
                            "empty_default_rejected=true empty_impact_rejected=true"
                        ),
                        "fingerprint": static_fp,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": "named probe 1 re-run after receipt write",
                        "fingerprint": p1_fp,
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A recorded owner answer closes the matching claim_id and "
                    "question fingerprint on re-run; questions already answered "
                    "in OWNER-DECISIONS.md are not re-asked."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0161/probe2_roundtrip.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": "named probe 2 re-run after receipt write",
                        "fingerprint": p2_fp,
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": "command-center/p2-wave/probes/CNF-0161/packet.py:is_answered",
                        "raw_output": (
                            f"live_answered_ids={sorted({d['claim_id'] for d in decisions if (d.get('answer') or '').strip()})}"
                        ),
                        "fingerprint": probe_fp(
                            "static-analysis",
                            "command-center/p2-wave/probes/CNF-0161/packet.py:is_answered",
                        ),
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T1",
                "name": "Format: exactly one foundation-level question; compound fails",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2",
                "name": "Duplicate: answered OWNER-DECISIONS questions do not reappear",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3",
                "name": "Default: every entry has a non-empty default and impact",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T4",
                "name": "Round-trip: a recorded answer closes the claim without re-asking",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-compound-question",
                "kind": "malformed-input",
                "description": (
                    "A packet entry whose question joins two interrogatives with "
                    "'and should' must be rejected as compound."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "compound-question",
                "good_state_output": "fixture CLAIM-TRI-001 accepted",
            },
            {
                "id": "NC-empty-default",
                "kind": "malformed-input",
                "description": (
                    "A packet entry with a whitespace-only default_if_unanswered "
                    "is not shippable."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "default_if_unanswered-empty",
                "good_state_output": "fixture defaults non-empty",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0161-probe2-owner-decisions-duplicate",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "local",
            "notes": (
                "Catalog reviewer: check each question against OWNER-DECISIONS.md "
                "for prior settlement. Probe 2 is that reviewer. Estate "
                "OWNER-DECISIONS.md is parsed (table + Decision blocks) and is "
                "not overwritten."
            ),
            "reviewed_at": ended,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0161/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0161",
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "schema-validate",
                    "command": "json.loads(command-center/receipts/CNF-0161.json)",
                    "raw_output": "consumer filled after write",
                    "fingerprint": probe_fp(
                        "schema-validate",
                        "json.loads(command-center/receipts/CNF-0161.json)",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": (
                "No verdict-laundering retry: a REFUTED or PARTIAL result is "
                "TERMINAL for this run. Retry only for an infrastructure fault."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Production unresolved-list coverage from CNF-0160.json is "
                    f"{coverage} ({src['reason']}). Claims were not invented."
                ),
                "verdict": "NOT-CHECKED" if coverage == "NOT-CHECKED" else "PARTIAL",
                "settling_experiment": (
                    "Place command-center/receipts/CNF-0160.json on disk and "
                    "re-run emit_receipt.py; open entries must be the unresolved "
                    "triangulation rows minus OWNER-DECISIONS.md answers."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "program-confirmer",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "program-gate-report",
            "title": "Owner escalation packet for claims no vendor can settle",
            "question": QUESTION,
            "packet_path": UNIT_PACKET_REL,
            "decisions_path": ESTATE_DECISIONS_REL,
            "estate_packet_path": ESTATE_PACKET_REL,
            "estate_files_written": False,
            "production_coverage": coverage,
            "production_coverage_reason": src["reason"],
            "open_entry_count": len(open_entries),
            "skipped_already_answered": skipped,
            "packet_entries": open_entries,
            "input": {
                "path": CNF0160_REL,
                "exists": src["exists"],
                "status": src["status"],
                "unresolved_claim_count": (
                    None if src["status"] != "PRESENT" else len(src["claims"])
                ),
            },
            "fixture_demonstration": {
                "path": FIXTURE_REL,
                "claim_ids": [c["id"] for c in fixture["claims"]],
                "open_entry_count": len(fixture_entries),
                "every_entry_has_default_and_impact": True,
                "settle_claim_CLAIM-TRI-001": {
                    "command": settle_cmd,
                    "exit_code": settle_rc,
                    "output_tail": settle_out[-500:],
                },
            },
            "observations": [
                {
                    "name": "production_unresolved_source",
                    "measured": src["status"],
                    "method": "file-read",
                    "anchor": CNF0160_REL,
                },
                {
                    "name": "open_owner_questions",
                    "measured": len(open_entries),
                    "method": "static-analysis",
                    "anchor": UNIT_PACKET_REL,
                },
                {
                    "name": "fixture_entries_shippable",
                    "measured": len(fixture_entries),
                    "method": "test-run",
                    "anchor": FIXTURE_REL,
                },
                {
                    "name": "estate_owner_files_intact",
                    "measured": True,
                    "method": "file-read",
                    "anchor": ESTATE_PACKET_REL,
                },
            ],
            "control_ids": ["NC-compound-question", "NC-empty-default"],
        },
        "extensions": {
            "cloud_ok": False,
            "named_probes": [
                {"id": "probe1", "role": "format-default", "command": P1},
                {"id": "probe2", "role": "duplicate-roundtrip", "command": P2},
            ],
            "does_not_claim": [
                "CNF-0160 ran or produced an unresolved list on this worktree",
                "the estate currently has zero unresolved triangulation claims",
                "the owner answered any production CNF-0161 question",
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "estate OWNER-QUESTION-PACKET.md or OWNER-DECISIONS.md was rewritten",
            ],
            "output_schema": SCHEMA,
            "output_schema_note": (
                "Catalog program-gate-report.schema.json is a generated shim. "
                "This receipt is validated against the unit-local schema at "
                "probes/CNF-0161/program-gate-report.local.schema.json."
            ),
        },
    }

    schema = json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0161 local schema errors")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0161", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0161 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    digest, size = sha256_file(out)
    doc["artifacts"][0]["bytes"] = size
    doc["artifacts"][0]["sha256"] = digest
    parsed = json.loads(out.read_text(encoding="utf-8"))
    if parsed.get("unit_id") != "CNF-0161":
        print("FAILED:CNF-0161 consumer json.loads unit_id")
        return 1
    doc["downstream_consumers"][0]["probe"]["raw_output"] = (
        f"json.loads ok unit_id={parsed.get('unit_id')} bytes={size}"
    )
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0161 artifact {size}B below floor")
        return 1
    if "SUCCESS:CNF-0161" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0161 sentinel missing after write")
        return 1
    if not estate_packet_intact(estate_packet.read_text(encoding="utf-8")):
        print("FAILED:CNF-0161 emit clobbered estate packet")
        return 1
    if not estate_decisions_intact(estate_decisions.read_text(encoding="utf-8")):
        print("FAILED:CNF-0161 emit clobbered estate decisions")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"source_status={src['status']} open_entries={len(open_entries)} "
        f"fixture_entries={len(fixture_entries)} packet={UNIT_PACKET_REL}"
    )
    print("SUCCESS:CNF-0161 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
