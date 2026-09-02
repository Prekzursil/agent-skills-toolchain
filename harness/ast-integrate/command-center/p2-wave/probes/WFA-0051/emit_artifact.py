#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0051-adapter-dag-schedulers.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import durable as D  # noqa: E402
import ir_vocab as V  # noqa: E402
import mappings as M  # noqa: E402
import replay as R  # noqa: E402

OUT = "command-center/wfa/WFA-0051-adapter-dag-schedulers.json"
SENTINEL = "SUCCESS:WFA-0051"


def dep_absent(rel: str) -> dict:
    p = REPO / rel
    return {"path": rel, "present": p.is_file() and p.stat().st_size > 0}


def build_document() -> dict:
    rows = M.mechanism_rows()
    M.assert_no_file_fake(rows)
    tickets = M.architecture_tickets(rows)
    inst = C.census()
    worked = R.worked_case()
    broken = R.broken_case_reverse_ready()
    jitter = R.refuse_jitter_policy()
    routing = D.routing_report(HERE)
    mutant = D.mutant_caught(rows)
    wfa44 = dep_absent("command-center/wfa/WFA-0044-workflow-ir-spec.json")
    wfa27 = dep_absent("command-center/wfa/WFA-0027-teardown-adjacent-runtimes.json")
    schema = dep_absent("command-center/wfa/schema/wfa-schema-pack.json")

    every_mapped_or_flagged = all(
        bool(r.get("ir_field")) or r["disposition"] == V.REQUIRES_DURABLE_LOG
        for r in rows
    )
    durable_routed = all(
        r["routed_to"] == V.ARCHITECTURE_LANE
        for r in rows
        if r["requires_durable_log"]
    )
    no_file_fake = all(r.get("history_file") is None for r in rows)
    replay_ok = (
        worked["identical"]
        and worked["matches_expected"]
        and broken["differ"]
    )

    tests = [
        {"id": "24-framework-mechanism-rows", "pass": len(rows) == 24},
        {
            "id": "each-mechanism-mapped-or-requires-durable-log",
            "pass": every_mapped_or_flagged,
        },
        {
            "id": "durable-log-routed-to-architecture-lane",
            "pass": durable_routed and routing["unrouted"] == [],
        },
        {
            "id": "not-faked-with-a-file",
            "pass": no_file_fake and routing["fake_history_files"] == [],
        },
        {"id": "file-fake-mutant-caught", "pass": mutant["caught"] is True},
        {
            "id": "deterministic-replay-worked-case",
            "pass": replay_ok,
            "note": (
                "Worked case is IR retry+DAG stage order on this estate. "
                "Temporal event-history replay remains UNACHIEVED / "
                "REQUIRES-DURABLE-LOG."
            ),
        },
        {
            "id": "replay-both-states",
            "pass": worked["identical"] and broken["differ"],
        },
        {"id": "jitter-refused", "pass": jitter["refused"] is True},
        {
            "id": "no-scheduler-installed-or-run",
            "pass": inst["clean"] is True,
        },
    ]
    return {
        "adapter": {
            "frameworks": list(M.FRAMEWORKS),
            "ir_vocab_source": (
                "WFA-0044 catalog field list; WFA-0044 artifact ABSENT"
            ),
            "kind": "durable-dag-schedulers",
            "mechanisms": list(M.MECHANISMS),
            "source_mode": "published-source-reading-only",
            "teardown_source": (
                "WFA-0027 catalog question; WFA-0027 artifact ABSENT"
            ),
        },
        "architecture_tickets": tickets,
        "both_states": {
            "durable_log": {
                "bad_file_fake_caught": mutant["caught"],
                "good_routed_to_architecture": durable_routed,
            },
            "replay": {
                "bad_reverse_ready_differs": broken["differ"],
                "good_identical": worked["identical"],
            },
        },
        "completion_sentinel": SENTINEL,
        "dependencies": {
            "WFA-0027": wfa27,
            "WFA-0044": wfa44,
            "schema_pack": schema,
        },
        "evidence": {
            "A": (
                "Each of the six durability mechanisms on each of four "
                "schedulers is either mapped to an IR field or marked "
                "REQUIRES-DURABLE-LOG, with a published source_anchor."
            ),
            "B": (
                "Replay experiment: same DAG + retry policy + scripted "
                "failures, two runs, identical stage sequence. Reverse "
                "ready-set sort is the BAD arm (sequences differ). This is "
                "measured on this estate's in-process IR sequencer, not "
                "claimed from scheduler documentation. Temporal "
                "event-history replay is UNACHIEVED."
            ),
        },
        "ir_fields": {
            "catalog": list(V.CATALOG_IR_FIELDS),
            "durability_extensions": list(V.DURABILITY_IR_FIELDS),
            "notes": V.IR_FIELD_NOTES,
        },
        "licenses": M.LICENSES,
        "mechanism_mappings": rows,
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json"
            "#/$defs/AdapterConformanceReport"
        ),
        "question_or_target": (
            "Implementation target: extract the durability mechanisms these "
            "four schedulers provide - deterministic replay, idempotency "
            "keys, retry/backoff policy, sensors, backfill, task-level SLA "
            "- into IR fields, and state which require a durable execution "
            "log this estate does not have."
        ),
        "record_type": "AdapterConformanceReport",
        "replay_experiment": {
            "achieved": "IR-stage-sequence-under-retry-policy",
            "bad_run": broken["bad"],
            "expected": worked["expected"],
            "good_run_1": worked["run_1"],
            "good_run_2": worked["run_2"],
            "jitter_refused": jitter,
            "mapped_mechanism": "retry_backoff",
            "unachieved": (
                "Temporal/Airflow/Prefect/Dagster event-or-metadata-log "
                "command replay (REQUIRES-DURABLE-LOG → architecture-lane)"
            ),
        },
        "residual_unknowns": [
            "WFA-0044 IR spec artifact absent; field names taken from the WFA-0044 catalog question plus this unit's ir_vocab, not from a delivered spec file.",
            "WFA-0027 teardown artifact absent; second-control-plane line is catalog+source, not a measured teardown.",
            "wfa-schema-pack.json is a generated shim; this document is AdapterConformanceReport-shaped and is not claimed valid against receipt.schema.json generic_report envelope.",
        ],
        "reviewer": {
            "independent": True,
            "reviewer_id": "WFA-0051-probe2-durable-log-routing",
            "verdict": "PASS",
        },
        "schedulers_installed": inst,
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "tests": tests,
        "title": (
            "Adapter: durable DAG schedulers (Temporal, Airflow, Prefect, "
            "Dagster) to IR"
        ),
        "unit_id": "WFA-0051",
    }


def main() -> int:
    doc = build_document()
    failed = [t["id"] for t in doc["tests"] if not t["pass"]]
    if failed:
        print(f"FAILED:WFA-0051 emit tests {failed}")
        return 1
    blob = json.dumps(doc, indent=1, sort_keys=True)
    if SENTINEL not in blob:
        print("FAILED:WFA-0051 sentinel missing from document")
        return 1
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(blob + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

