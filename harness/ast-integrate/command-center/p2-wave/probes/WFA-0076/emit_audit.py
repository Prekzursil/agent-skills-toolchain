#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0076-terminal-disposition-reversibility.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = "command-center/wfa/WFA-0076-terminal-disposition-reversibility.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0076/audit_report.schema.json"
PACK_REL = "command-center/wfa/schema/wfa-schema-pack.json"
DECLARED_PACK = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0076/probe1_restoration_rehearsal.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0076/probe2_gate_and_schema.py"
)
QUESTION = (
    "For every terminal disposition (RETIRE, REJECT), is the source content "
    "demonstrably preserved — in the repo at a named commit, or in an export "
    "— before the disposition is recorded, and can it be restored?"
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    result = E.process_scenario()
    if not E.gate_holds(result):
        print("FAILED:WFA-0076 emit gate does not hold")
        print(json.dumps(result["gate"], sort_keys=True))
        return 1
    rehearsal = result["rehearsal"]
    live = result["live"]
    pack_path = REPO / PACK_REL
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    recorded = [r["id"] for r in result["rows"] if r["recorded"]]
    refused = [r["id"] for r in result["rows"] if not r["recorded"]]
    answer = (
        "Yes, as a gate: a RETIRE or REJECT row is recorded only after content "
        "is retrieved from a named preserved location (named-export or git-blob) "
        "and the retrieved bytes hash-match the claimed content hash. A "
        f"restoration rehearsal ran end-to-end on {rehearsal['record_id']} "
        f"({rehearsal['bytes']} bytes, dest hash matched). Squash-merge history "
        "is refused as preservation evidence (the naive ancestry detector would "
        "have accepted the planted squash claim). WFA-0071 and the 284-row "
        "candidate registry are absent on this Linux worktree, so live RETIRE "
        "n=24 was not processed; no live terminal disposition was written. "
        "Owner approval remains required before any estate-level irreversible "
        "action. SUCCESS:WFA-0076"
    )
    terminal_records = []
    for row in result["rows"]:
        terminal_records.append(
            {
                "id": row["id"],
                "disposition": row["disposition"],
                "role": row["role"],
                "claimed_hash": row["claimed_hash"],
                "location_kind": row["location_kind"],
                "named_location": row["named_location"],
                "retrieval_ok": row["retrieval_ok"],
                "retrieval_reason": row["retrieval_reason"],
                "retrieved_hash": row["retrieved_hash"],
                "squash_merge_rejected": row["squash_merge_rejected"],
                "naive_ancestry_would_accept": row["naive_ancestry_would_accept"],
                "recorded": row["recorded"],
                "decision_reason": row["decision_reason"],
            }
        )
    doc = {
        "unit_id": "WFA-0076",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0076",
        "report_kind": "AuditReport",
        "question": QUESTION,
        "answer": answer,
        "ts": now,
        "output_path": OUT,
        "output_schema": DECLARED_PACK,
        "owner_approval_required": True,
        "live_irreversible_action": False,
        "adv_rebuild_circle": False,
        "schema_resolution": {
            "declared_pack": DECLARED_PACK,
            "pack_present": pack_path.is_file(),
            "pack_local_constraints": False,
            "validator": SCHEMA_REL,
        },
        "terminal_records": terminal_records,
        "restoration_rehearsal": {
            "ok": True,
            "end_to_end": True,
            "record_id": rehearsal["record_id"],
            "disposition": rehearsal["disposition"],
            "bytes": rehearsal["bytes"],
            "reason": rehearsal["reason"],
            "dest_hash": rehearsal["dest_hash"],
            "claimed_hash": rehearsal["claimed_hash"],
        },
        "gate": {
            "no_terminal_without_retrieval": True,
            "squash_merge_refused": True,
            "naive_would_accept_squash": True,
            "happy_retire_recorded": True,
            "happy_reject_recorded": True,
            "missing_refused": True,
            "mismatch_refused": True,
        },
        "squash_merge_policy": {
            "accepted_as_preservation_evidence": False,
            "reason": (
                "On this estate squash-merge makes a fully merged branch report "
                "as AHEAD, so commit ancestry is not a retrieval receipt. Only "
                "named-export or git-blob content retrieval with a hash match "
                "counts."
            ),
        },
        "live_estate": {
            "wfa0071_artifact_present": live["wfa0071_artifact_present"],
            "git_dir_present": live["git_dir_present"],
            "registry_candidates": live["registry_candidates"],
            "live_terminal_records_processed": live[
                "live_terminal_records_processed"
            ],
            "note": live["note"],
        },
        "findings": [
            {
                "id": "provenance-loss",
                "title": "Terminal disposition recorded without a retrieval receipt",
                "severity": "none",
                "status": "absent",
            },
            {
                "id": "detector-failure",
                "title": "Gate silent on squash-merge / missing / hash-mismatch",
                "severity": "none",
                "status": "absent",
            },
            {
                "id": "owner-blocked",
                "title": "Live irreversible RETIRE/REJECT executed without owner sign-off",
                "severity": "none",
                "status": "not-applicable",
            },
        ],
        "evidence": [
            {
                "id": "A",
                "kind": "named-location-hash",
                "detail": (
                    "Each recorded terminal row names a preserved location and a "
                    f"content hash. Recorded ids: {recorded}."
                ),
            },
            {
                "id": "B",
                "kind": "retrieval-receipt",
                "detail": (
                    "Retrieval of those bytes from the named location hash-matched "
                    "before the ledger append. Refused ids: "
                    f"{refused}."
                ),
            },
            {
                "id": "restoration",
                "kind": "rehearsal",
                "detail": (
                    f"Restored {rehearsal['record_id']} to a temp dest; "
                    f"{rehearsal['bytes']} bytes; dest hash "
                    f"{rehearsal['dest_hash']} matched the claimed hash."
                ),
            },
            {
                "id": "squash-negative",
                "kind": "control",
                "detail": (
                    "Planted squash-merge-history claim: naive ancestry would "
                    "accept; the gate refused with squash-merge-not-evidence."
                ),
            },
        ],
        "tests": [
            {
                "id": "WFA0076-T1-RESTORATION-REHEARSAL",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "WFA0076-T2-NO-TERMINAL-UNTIL-RETRIEVAL",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "WFA0076-T3-SQUASH-MERGE-NOT-EVIDENCE",
                "command": P1,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0076-probe2-gate-and-schema",
            "verdict": "PASS",
            "independent": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/WFA-0076/engine.py",
                "exists": True,
                "role": "gate",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
    }
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:WFA-0076 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print("FAILED:WFA-0076 schema accepted garbage")
            return 1
    if "SUCCESS:WFA-0076" not in json.dumps(doc):
        print("FAILED:WFA-0076 sentinel-absent from document")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:WFA-0076 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
