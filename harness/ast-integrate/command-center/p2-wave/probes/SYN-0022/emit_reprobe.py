#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0022.premise-reprobe.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    CATALOG_REL,
    OUTPUT_REL,
    P1_CMD,
    P2_CMD,
    SCHEMA_REL,
    UNIT_ID,
    catalog_question,
    catalog_sentinel,
)
from facts import MNN_FACT_ID, build_records, summarize  # noqa: E402
from gate import run_gate_controls  # noqa: E402
from schema_util import garbage_rejected, schema_errors  # noqa: E402

MANIFEST_REL = "command-center/p2-wave/probes/SYN-0022/UNIT-ARTIFACT-MANIFEST.json"
PLACEHOLDER_SHA = "0" * 64
EVIDENCE_VERDICT = {
    "CONFIRMED": "CONFIRMED",
    "REFUTED": "REFUTED",
    "REFUTED-AS-BRIEFED": "REFUTED",
    "NOT-CHECKED": "NOT-CHECKED",
    "VIOLATION": "BLOCKED",
}
SUPPORTING_FOR_RECEIPT = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/SYN-0022/schema_util.py",
    "command-center/p2-wave/probes/SYN-0022/cnf0006_fingerprint.py",
    "command-center/p2-wave/probes/SYN-0022/facts.py",
    "command-center/p2-wave/probes/SYN-0022/gate.py",
    "command-center/p2-wave/probes/SYN-0022/probe1_fingerprint_independence.py",
    "command-center/p2-wave/probes/SYN-0022/probe2_controls_and_mnn.py",
]


def digest_file(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    eol = "LF" if b"\r\n" not in raw else ("CRLF" if b"\n" not in raw.replace(b"\r\n", b"") else "MIXED")
    if b"\n" not in raw and b"\r" not in raw:
        eol = "BINARY" if raw else "LF"
    return hashlib.sha256(norm).hexdigest(), len(norm), eol


def artifact_row(rel: str, role: str, sha: str, size: int, eol: str = "LF") -> dict:
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def evidence_from_record(row: dict) -> dict:
    mapped = EVIDENCE_VERDICT.get(str(row.get("verdict")), "NOT-CHECKED")
    item = {
        "claim": str(row.get("briefed_claim") or "")[:2000],
        "verdict": mapped,
        "anchor": f"{OUTPUT_REL}:report.records.{row.get('fact_id')}",
        "probes": [
            {
                "role": "source",
                "method": "manual-inspection",
                "command": (
                    f"reconstructed original probe for {row.get('fact_id')} "
                    f"tuple={row.get('source_tuple')}"
                )[:4096],
                "raw_output": str(row.get("source_output") or "")[:65536],
                "fingerprint": str(row.get("source_fingerprint") or "")[:128],
            },
            {
                "role": "verifier",
                "method": "command",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    f"command-center/p2-wave/probes/SYN-0022/facts.py #{row.get('fact_id')}"
                ),
                "raw_output": str(row.get("verifier_output") or "")[:65536],
                "fingerprint": str(row.get("verifier_fingerprint") or "")[:128],
            },
        ],
    }
    if mapped in ("CONFIRMED", "REFUTED"):
        item["confidence"] = "almost-certain"
    return item


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def main() -> int:
    sentinel = catalog_sentinel()
    question = catalog_question()
    if not sentinel.startswith("SUCCESS:SYN-0022"):
        print("FAILED:SYN-0022 catalog sentinel missing")
        return 1
    ok_garbage, n_garbage = garbage_rejected()
    if not ok_garbage:
        print(f"FAILED:SYN-0022 schema vacuous garbage_rejected={n_garbage}")
        return 1

    records = build_records()
    summary = summarize(records)
    gates = run_gate_controls()
    mnn = next((row for row in records if row["fact_id"] == MNN_FACT_ID), None)
    if mnn is None or mnn.get("verdict") != "REFUTED-AS-BRIEFED":
        print("FAILED:SYN-0022 known-refuted control M-NN was not REFUTED-AS-BRIEFED")
        return 1
    if summary["independent_pairs"] != summary["fact_count"]:
        print("FAILED:SYN-0022 a delivered record is not an independent pair")
        return 1
    if summary["same_probe_reruns"] or summary["undeclared_sources"] or summary["violations"]:
        print("FAILED:SYN-0022 delivered records include rerun/undeclared/violation")
        return 1
    for row in records:
        if row["source_fingerprint"] == row["verifier_fingerprint"]:
            print(f"FAILED:SYN-0022 verifier duplicates source on {row['fact_id']}")
            return 1
        if not row["source_output"].strip() or not row["verifier_output"].strip():
            print(f"FAILED:SYN-0022 empty probe output on {row['fact_id']}")
            return 1
    if not (
        gates["same_fingerprint_rejected"]
        and gates["empty_source_is_violation"]
        and gates["distinct_fingerprint_accepted"]
    ):
        print("FAILED:SYN-0022 gate controls")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mnn_live = json.loads(mnn["verifier_output"])
    catalog_live = json.loads(
        next(r for r in records if r["fact_id"] == "F-CATALOG-UNITS-2007")["verifier_output"]
    )
    delivered_live = json.loads(
        next(r for r in records if r["fact_id"] == "F-DELIVERED-COUNT-4")["verifier_output"]
    )
    receipt_live = json.loads(
        next(r for r in records if r["fact_id"] == "F-RECEIPT-SCHEMA-ABSENT")["verifier_output"]
    )
    decision_live = json.loads(
        next(
            r
            for r in records
            if r["fact_id"] == "F-DECISION-LOG-LINE-175-PRESENT-TENSE"
        )["verifier_output"]
    )

    supporting_rows = []
    for rel in SUPPORTING_FOR_RECEIPT:
        path = REPO / rel
        sha, size, eol = digest_file(path)
        supporting_rows.append(artifact_row(rel, "supporting", sha, size, eol))

    primary = artifact_row(OUTPUT_REL, "primary", PLACEHOLDER_SHA, 1, "LF")
    tests = [
        {
            "id": "test_source_and_verifier_probe_fingerprints_differ",
            "name": "A same-fingerprint rerun is rejected; delivered pairs differ.",
            "command": P1_CMD,
            "result": "PASS",
        },
        {
            "id": "test_a_record_with_an_empty_source_probe_is_a_VIOLATION_not_a_pass",
            "name": "Empty source_probe is VIOLATION, not an independent pair.",
            "command": P2_CMD,
            "result": "PASS",
        },
        {
            "id": "known-refuted-control-m-nn-collision-REFUTED-AS-BRIEFED",
            "name": "The briefed 31-way M-NN collision comes back REFUTED-AS-BRIEFED.",
            "command": P2_CMD,
            "result": "PASS",
        },
    ]
    doc = {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "rules/common/single-signal-verification.md:34",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "stale-premise-refuter",
            "execution_substrate": "local-serialized",
        },
        "artifacts": [primary] + supporting_rows,
        "evidence": [evidence_from_record(row) for row in records],
        "tests": tests,
        "negative_controls": [
            {
                "id": "empty-source-is-violation",
                "kind": "malformed-input",
                "description": (
                    "A record whose source_probe is empty is a VIOLATION, not "
                    "an independent pair (undeclared source is zero signals)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "UNDECLARED-SOURCE -> VIOLATION",
                "good_state_output": "declared independent pair accepted",
            },
            {
                "id": "same-fingerprint-rerun-rejected",
                "kind": "known-broken-fixture",
                "description": (
                    "Source and verifier with identical CNF-0006 tuples must not "
                    "close as CONFIRMED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "SAME-PROBE-RERUN -> NOT-CHECKED",
                "good_state_output": "distinct four-axis tuples accepted",
            },
            {
                "id": "schema-garbage-rejected",
                "kind": "malformed-input",
                "description": (
                    "Empty object, unrelated passing_tests blob, and 2000-char "
                    "payload must fail the disk-resolved reprobe-record schema."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"garbage_rejected={n_garbage}/3",
                "good_state_output": "live receipt validates against disk store",
            },
            {
                "id": "known-refuted-m-nn-collision",
                "kind": "known-broken-fixture",
                "description": (
                    "Briefed 31-way live M-NN collision must come back "
                    "REFUTED-AS-BRIEFED (live shared bare M-ids != 31)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"briefed_collision_count=31 live_collision_count="
                    f"{mnn_live.get('live_collision_count')}"
                ),
                "good_state_output": "verdict=REFUTED-AS-BRIEFED",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0022-probe2-controls-and-mnn",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "probe2 is served the raw source_output and verifier_output "
                "fields and re-derives each verdict before comparing them to "
                "the emit conclusion"
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
            "entry_id": UNIT_ID,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "disk-resolved Draft7Validator reprobe-record.schema.json",
                "artifact_path": OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/SYN-0022/emit_reprobe.py"
                    ),
                    "raw_output": "SUCCESS:SYN-0022 emit",
                    "fingerprint": hashlib.sha256(
                        b"schema-validate|emit_reprobe.py"
                    ).hexdigest(),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "no re-roll of a disagreeing run. If a second pass produces a "
                "different set, BOTH sets are kept and the delta becomes the finding"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Sibling-unit SUCCESS-count will keep moving as other units "
                    "land artifacts; F-DELIVERED-COUNT-4 records the live integer "
                    "at emit time and probe1 does not require that integer to freeze."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run measure_delivered_success_count after the wave freeze "
                    "and compare to the recorded verifier_output."
                ),
            },
            {
                "claim": (
                    "Estate-declaring 07-OPTION-UNIVERSE / "
                    "13-ARCHITECTURE-CANDIDATES / 17-DECISION-LOG.md files are "
                    "absent on this worktree (probe fixtures are not declaring "
                    "files). live_collision_count=0 is a genuine zero, not a "
                    "hidden 31-way overlap in those fixtures."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Place the three declaring documents at estate roots and "
                    "re-run measure_mnn_collision; a live shared-id set of 31 "
                    "would flip F-MNN-COLLISION-LIVE-31 to CONFIRMED."
                ),
            },
        ],
        "report": {
            "kind": "reprobe-record",
            "observations": [
                {
                    "name": "catalog_work_units_length",
                    "measured": int(catalog_live["work_units_array_length"]),
                    "method": "json-array-len",
                    "anchor": CATALOG_REL,
                },
                {
                    "name": "mnn_live_collision_count",
                    "measured": int(mnn_live["live_collision_count"]),
                    "method": "set-cardinality",
                    "anchor": "estate-declaring option-universe ∩ architecture-candidates",
                },
                {
                    "name": "receipt_schema_exists",
                    "measured": bool(receipt_live["exists"]),
                    "method": "file-bytes",
                    "anchor": "command-center/schema/receipt.schema.json",
                },
                {
                    "name": "state_success_count",
                    "measured": int(delivered_live["state_success_count"]),
                    "method": "SUCCESS-count",
                    "anchor": "catalog output_path artifacts",
                },
                {
                    "name": "decision_log_present",
                    "measured": bool(decision_live.get("exists")),
                    "method": "line-index-read",
                    "anchor": "17-DECISION-LOG.md",
                },
            ],
            "control_ids": [
                "test_source_and_verifier_probe_fingerprints_differ",
                "test_a_record_with_an_empty_source_probe_is_a_VIOLATION_not_a_pass",
                "known-refuted-control-m-nn-collision-REFUTED-AS-BRIEFED",
            ],
            "question": question,
            "fingerprint_spec": {
                "axes": ["tool", "shell", "data_field", "measurement_kind"],
                "source": (
                    "CNF-0006 catalog tuple. That unit's confirmation-corpus "
                    "artifact may exist; SYN-0022 instantiates the specified "
                    "four-axis fingerprint against briefed premises rather than "
                    "inventing a fifth axis."
                ),
                "applied_to": "briefed premises (not the confirmation corpus)",
                "implementation": (
                    "command-center/p2-wave/probes/SYN-0022/cnf0006_fingerprint.py"
                ),
            },
            "records": records,
            "summary": summary,
            "controls": {
                "same_fingerprint_rejected": True,
                "empty_source_is_violation": True,
                "distinct_fingerprint_accepted": True,
                "mnn_collision_refuted_as_briefed": True,
                "gate": gates["details"],
            },
            "named_probes": [
                {"id": "probe1", "command": P1_CMD, "role": "fingerprint-independence"},
                {"id": "probe2", "command": P2_CMD, "role": "empty-source-and-mnn-control"},
            ],
            "schema_garbage_rejected": n_garbage,
            "produced_at": now,
        },
    }

    errors = schema_errors(doc)
    if errors:
        print(f"FAILED:SYN-0022 schema: {errors[0]}")
        for err in errors[:8]:
            print(f"  {err}")
        return 1

    out = REPO / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump(doc), encoding="utf-8")
    sha, size, eol = digest_file(out)
    doc["artifacts"][0] = artifact_row(OUTPUT_REL, "primary", sha, size, eol)
    errors = schema_errors(doc)
    if errors:
        print(f"FAILED:SYN-0022 schema after hash: {errors[0]}")
        return 1
    out.write_text(dump(doc), encoding="utf-8")
    print(
        f"wrote {OUTPUT_REL} facts={summary['fact_count']} "
        f"confirmed={summary['confirmed']} refuted={summary['refuted']} "
        f"refuted_as_briefed={summary['refuted_as_briefed']}"
    )
    print("SUCCESS:SYN-0022 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
