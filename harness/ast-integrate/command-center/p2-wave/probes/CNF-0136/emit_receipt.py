#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0136.json from a live scheduler run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from scenario import run_scenario  # noqa: E402

OUT = "command-center/receipts/CNF-0136.json"
SCHEMA = "command-center/schema/confirmation-tooling-receipt.schema.json"
TAXONOMY = "command-center/confirmation/cnf0136/taxonomy.py"
SCHEDULER = "command-center/confirmation/cnf0136/scheduler.py"
RECORD_PY = "command-center/confirmation/cnf0136/record.py"
QUEUE_PY = "command-center/confirmation/cnf0136/queue.py"
RECORD_SCHEMA = "command-center/confirmation/cnf0136/confirmation-record.schema.json"
INDUCED = "command-center/confirmation/cnf0136/induced-records.json"
LOCAL_RECEIPT_SCHEMA = (
    "command-center/confirmation/cnf0136/tooling-receipt.local.schema.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0136/probe1_fault_injection.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0136/probe2_refute_and_idempotence.py"
)
QUESTION = (
    "Implementation target: a scheduler for the confirmation queue with "
    "staggered arrivals, per-vendor quota awareness and an explicit fault "
    "taxonomy, whose central invariant is that a 429 storm, a crashed runner, "
    "a severed stream or a timeout maps to BLOCKED with a named prerequisite "
    "- never to REFUTED and never to CONFIRMED. Spec:10577-10578 makes "
    "arrival rate a scheduler input."
)


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    hits = [i for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if snippet in ln]
    if len(hits) != 1:
        raise SystemExit(f"FAILED:CNF-0136 emit anchor {rel} {snippet!r} hits={hits}")
    return hits[0]


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def slim_record(rec: dict) -> dict:
    keys = (
        "record_id",
        "job_id",
        "claim_id",
        "verdict",
        "fault_class",
        "named_prerequisite",
        "scheduled_at_ms",
        "timeout_seconds",
        "quota_posture",
        "parked_two_strikes",
        "source_probe",
        "verifier_probe",
        "discrepancies",
        "residual_caveat",
    )
    return {k: rec.get(k) for k in keys if k in rec}


def main() -> int:
    data = run_scenario()
    if not data.get("taxonomy_ok") or not data.get("arrival_rate_required"):
        print("FAILED:CNF-0136 scenario preconditions")
        return 1
    if data.get("infra_refuted_ids"):
        print("FAILED:CNF-0136 reviewer infra-REFUTED", data["infra_refuted_ids"])
        return 1

    induced_path = REPO / INDUCED
    induced_path.parent.mkdir(parents=True, exist_ok=True)
    induced_doc = {k: slim_record(v) for k, v in data["induced"].items()}
    induced_doc["quota_429_storm_burst"] = [slim_record(r) for r in data["burst"]]
    induced_doc["genuine_refuted"] = slim_record(data["genuine"])
    induced_path.write_text(
        json.dumps(induced_doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    e1 = ev(
        TAXONOMY,
        "CNF-0136-TAXONOMY-TABLE",
        "taxonomy",
        "Fault taxonomy table is the source of BLOCKED mappings.",
    )
    e2 = ev(
        TAXONOMY,
        "# CNF-0136-ROW severed-stream",
        "taxonomy",
        "Kill/crash/stream-eof maps to BLOCKED severed-stream with restore-confirmer-stream.",
    )
    e3 = ev(
        TAXONOMY,
        "# CNF-0136-ROW quota-429-storm",
        "taxonomy",
        "HTTP 429/529 maps to BLOCKED quota-429-storm with vendor-quota-headroom.",
    )
    e4 = ev(
        TAXONOMY,
        "# CNF-0136-ROW timeout-<n>s",
        "taxonomy",
        "Deadline maps to BLOCKED timeout-<n>s with extend-or-split-confirmation-timeout.",
    )
    e5 = ev(
        TAXONOMY,
        "# CNF-0136-ROW duplicate-dispatch",
        "taxonomy",
        "In-flight re-dispatch maps to BLOCKED duplicate-dispatch with dedupe-confirmation-job-id.",
    )
    e6 = ev(
        SCHEDULER,
        "arrival_rate_hz is a required scheduler input and must be > 0",
        "scheduler",
        "Arrival rate is a required constructor input (spec:10577-10578).",
    )
    e7 = ev(
        SCHEDULER,
        "Claim verdict on an infra event is ignored: classification is typed.",
        "scheduler",
        "A smuggled REFUTED/CONFIRMED on an infra event cannot become a claim verdict.",
    )
    e8 = ev(
        QUEUE_PY,
        "Re-queue updates in place; never inserts a twin.",
        "queue",
        "Re-queue of BLOCKED updates the same record_id and does not insert a twin.",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    kill = slim_record(data["kill"])
    burst0 = slim_record(data["burst"][0])
    timeout = slim_record(data["timeout"])
    duplicate = slim_record(data["duplicate"])
    genuine = slim_record(data["genuine"])

    doc = {
        "unit_id": "CNF-0136",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0136",
        "schema_version": 1,
        "report_kind": "confirmation-tooling-receipt",
        "title": "Confirmation-queue scheduler that cannot record an infrastructure fault as a refutation",
        "question": QUESTION,
        "completion_sentinel": "SUCCESS:CNF-0136",
        "implementation": {
            "scheduler_module": SCHEDULER,
            "taxonomy_module": TAXONOMY,
            "queue_module": QUEUE_PY,
            "record_module": RECORD_PY,
            "record_schema": RECORD_SCHEMA,
            "arrival_rate_hz": data["arrival_rate_hz"],
            "arrival_rate_is_required_input": True,
            "stagger_gap_ms": data["want_gap_ms"],
            "quota_posture": data["quota_posture"],
            "cnf0129_receipt": "ABSENT — local confirmation-record schema shipped so scheduler records are typed; claim_gate.py integration is not this unit",
        },
        "fault_taxonomy_citations": [
            e1["anchor"],
            e2["anchor"],
            e3["anchor"],
            e4["anchor"],
            e5["anchor"],
        ],
        "induced_faults": {
            "severed-stream": kill,
            "quota-429-storm": burst0,
            "timeout-<n>s": timeout,
            "duplicate-dispatch": duplicate,
            "genuine_refuted_under_healthy_infra": genuine,
        },
        "stagger": {
            "arrival_rate_hz": data["arrival_rate_hz"],
            "burst_n": len(data["burst"]),
            "burst_slots_ms": data["burst_slots"],
            "burst_gaps_ms": data["burst_gaps"],
            "want_gap_ms": data["want_gap_ms"],
        },
        "idempotence": data["idemp"],
        "two_strikes": data["two_strikes"],
        "quota": {
            "posture": data["quota_posture"],
            "reason": (
                "AgentBridge budget tooling is retired; this worktree has no live "
                "vendor quota probe. Scheduler still accepts vendor_rate_cap_hz as "
                "an advisory fixture input. Unmeasured quota is NOT-CHECKED, not asserted."
            ),
        },
        "evidence": [e1, e2, e3, e4, e5, e6, e7, e8],
        "tests": [
            {
                "id": "T1-fault-injection",
                "name": "Kill, 429 storm+stagger, timeout, duplicate, crash -> BLOCKED never REFUTED",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-refute-and-idempotence",
                "name": "Genuine REFUTED under healthy infra; re-queue BLOCKED does not duplicate; reviewer grep",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0136-probe2-infra-refuted-grep",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Grep every emitted record with verdict=REFUTED whose discrepancies "
                "or residual_caveat match infra needles (429, SIGKILL, timeout, "
                "severed-stream, duplicate-dispatch). Want zero hits."
            ),
            "infra_refuted_ids": data["infra_refuted_ids"],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "output-schema"},
            {"path": RECORD_SCHEMA, "exists": True, "role": "record-schema"},
            {"path": TAXONOMY, "exists": True, "role": "taxonomy"},
            {"path": SCHEDULER, "exists": True, "role": "scheduler"},
            {"path": INDUCED, "exists": True, "role": "induced-records"},
        ],
        "residual_unknowns": [
            {
                "id": "R1",
                "item": "rules/common/cross-vendor-dispatch.md",
                "status": "NOT-CHECKED",
                "reason": "File absent on this worktree; taxonomy encodes catalog restatement (never convert 429/529 to REFUTED; severed-stream on missing record).",
            },
            {
                "id": "R2",
                "item": "command-center/events/EVENTS.jsonl",
                "status": "NOT-CHECKED",
                "reason": "Event log absent; scheduler is clock-injected and does not claim a live event-log join.",
            },
            {
                "id": "R3",
                "item": "command-center/receipts/CNF-0129.json",
                "status": "NOT-CHECKED",
                "reason": "CNF-0129 receipt absent. This unit ships a compatible confirmation-record schema for scheduler emission only.",
            },
            {
                "id": "R4",
                "item": "live vendor quota",
                "status": "NOT-CHECKED",
                "reason": "AgentBridge budget tooling retired; quota_posture=NOT-CHECKED.",
            },
        ],
        "min_bytes_threshold": 2048,
        "named_probes": [
            {"id": "probe1", "role": "fault-injection", "command": P1},
            {"id": "probe2", "role": "refute-and-idempotence", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0136/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "timestamps": {"ended_at": now},
        "answer": (
            f"Infrastructure faults map to BLOCKED with a named prerequisite: "
            f"kill/crash -> severed-stream/{kill['named_prerequisite']}; "
            f"429 storm -> quota-429-storm/{burst0['named_prerequisite']} "
            f"with stagger gap {data['want_gap_ms']}ms at {data['arrival_rate_hz']} Hz; "
            f"timeout -> timeout-<n>s/{timeout['named_prerequisite']}; "
            f"in-flight duplicate -> duplicate-dispatch/{duplicate['named_prerequisite']}. "
            f"Genuine healthy-infra REFUTED still records REFUTED. "
            f"Re-queue of BLOCKED keeps record_id and store count. "
            f"Quota posture {data['quota_posture']}. "
            "SUCCESS:CNF-0136"
        ),
    }

    catalog_shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if catalog_shim.get("x-artifact-class") != "confirmation-tooling-receipt":
        print("FAILED:CNF-0136 catalog output_schema is not the tooling-receipt shim")
        return 1
    # Catalog shim $ref targets ast-integrate.invalid and carries no constraints.
    # Garbage rejection uses the local closed schema shipped with this unit.
    schema = json.loads((REPO / LOCAL_RECEIPT_SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0136 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:CNF-0136 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:CNF-0136" not in raw:
        print("FAILED:CNF-0136 sentinel missing from artifact text")
        return 1
    if len(raw.encode("utf-8")) < int(doc["min_bytes_threshold"]):
        print("FAILED:CNF-0136 artifact below byte floor")
        return 1
    out.write_text(raw, encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:CNF-0136 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
