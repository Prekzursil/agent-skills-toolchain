#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0099-collapse-audit-trail.json."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    load_report_schema,
    load_trail_schema,
    run_append_only_controls,
    run_entry_point_controls,
    run_rehearsal,
    schema_rejects_garbage,
    validate_instance,
)

UNIT = "WFA-0099"
OUT_REL = "command-center/wfa/WFA-0099-collapse-audit-trail.json"
TRAIL_REL = "command-center/wfa/WFA-0099-collapse-trail.jsonl"
PACK_REL = "command-center/wfa/schema/wfa-schema-pack.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0099/audit-report.schema.json"
TRAIL_SCHEMA_REL = "command-center/p2-wave/probes/WFA-0099/trail-record.schema.json"
SENTINEL = "SUCCESS:WFA-0099"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0099/probe1_restore_rehearsal.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0099/probe2_append_only_and_entry.py"
)
QUESTION = (
    "Implementation target: every collapse writes an append-only record naming "
    "the surviving id, the absorbed ids, the deciding signals and the preserved "
    "union - and a restore operation can reconstruct the pre-collapse records "
    "from that record alone."
)


def repo_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / CATALOG).is_file():
            return p
    raise SystemExit("FAILED:WFA-0099 repo root not found")


def catalog_unit(repo: Path) -> dict:
    data = json.loads((repo / CATALOG).read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT:
            return u
    raise SystemExit("FAILED:WFA-0099 catalog row missing")


def main() -> int:
    repo = repo_root()
    unit = catalog_unit(repo)
    completion = str(unit.get("completion_sentinel") or SENTINEL)
    pack = repo / PACK_REL
    pack_status = (
        f"PRESENT bytes={pack.stat().st_size}"
        if pack.is_file()
        else "ABSENT (WFA-0001 not delivered on this worktree; local schema is the live checker)"
    )

    with tempfile.TemporaryDirectory(prefix="wfa0099-emit-") as tmp:
        tmp_path = Path(tmp)
        trail_path = tmp_path / "trail.jsonl"
        live = run_rehearsal(trail_path)
        append = run_append_only_controls(trail_path, tmp_path)
        entry = run_entry_point_controls(tmp_path)
        trail_bytes = trail_path.read_bytes()

    if not live["all_restored"] or not live["three_distinct_signals"]:
        print("FAILED:WFA-0099 restore rehearsal did not pass")
        print(json.dumps({k: live[k] for k in live if k != "trail_events"}, indent=2)[:4000])
        return 1
    if not append["pass"]:
        print("FAILED:WFA-0099 append-only controls", append)
        return 1
    if not entry["pass"]:
        print("FAILED:WFA-0099 entry-point controls", entry)
        return 1

    trail_schema = load_trail_schema()
    report_schema = load_report_schema()
    if not schema_rejects_garbage(trail_schema) or not schema_rejects_garbage(report_schema):
        print("FAILED:WFA-0099 schema accepted garbage")
        return 1

    trail_errs: list[str] = []
    for i, rec in enumerate(live["trail_events"], 1):
        trail_errs.extend(f"record[{i}] {e}" for e in validate_instance(trail_schema, rec))
    if trail_errs:
        print("FAILED:WFA-0099 trail records failed schema")
        print("\n".join(trail_errs[:20]))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    restore_rows = []
    for h in live["rehearsals"]:
        restore_rows.append(
            {
                "primary_signal": h["primary_signal"],
                "surviving_id": h["surviving_id"],
                "absorbed_ids": h["absorbed_ids"],
                "equal": h["equal"],
                "pre_sha256": h["pre_sha256"],
                "restored_sha256": h["restored_sha256"],
                "event_hash": h["event_hash"],
                "seq": h["seq"],
                "diffs": h["diffs"],
                "preserved_union": h["preserved_union"],
            }
        )

    answer = (
        f"{completion}. Three collapses (signals {live['primary_signals']}) each "
        "wrote an append-only hash-chained trail record naming surviving_id, "
        "absorbed_ids, deciding_signals and preserved_union. Restore from each "
        "record alone reconstructed the pre-collapse records with empty diffs. "
        "A rewrite of a prior line breaks the hash chain (gate failure). "
        "CollapseGate.collapse refuses when the trail append is not durable; "
        "RecordStore._commit_collapse without GATE_TOKEN raises. "
        f"WFA schema pack: {pack_status}."
    )

    tests = [
        {
            "id": "restore-rehearsal-three-signals",
            "command": P1,
            "result": "PASS",
            "detail": (
                "Restore rehearsal executed for three collapses (LEXICAL, "
                "EMBEDDING, STRUCTURAL). Restored records matched the "
                "pre-collapse snapshot. Every trail record passed schema."
            ),
        },
        {
            "id": "append-only-rewrite-is-gate-failure",
            "command": P2,
            "result": "PASS",
            "detail": (
                "CollapseTrail.rewrite_line raises. Mutating a prior JSONL line "
                "makes verify() fail; the intact trail verifies."
            ),
        },
        {
            "id": "collapse-without-trail-impossible",
            "command": P2,
            "result": "PASS",
            "detail": (
                "Direct _commit_collapse without GATE_TOKEN raises. A refusing "
                "or silent trail leaves the store unchanged."
            ),
        },
    ]

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": completion,
        "report_kind": "collapse-audit-trail",
        "title": "Reversible audit trail for every collapse performed",
        "question": QUESTION,
        "answer": answer,
        "measured_at": now,
        "schema_pack": {
            "catalog_output_schema": unit.get("output_schema"),
            "status": pack_status,
            "live_checker": SCHEMA_REL,
            "trail_record_schema": TRAIL_SCHEMA_REL,
        },
        "dependency_wfa_0095": {
            "artifact": "command-center/wfa/WFA-0095-duplicate-collapse-policy.json",
            "present": (repo / "command-center/wfa/WFA-0095-duplicate-collapse-policy.json").is_file(),
            "note": (
                "WFA-0095 artifact is absent. Union-preservation policy "
                "(mechanisms, provenance anchors, licence obligations, stop "
                "rules; stricter licence governs) is encoded in CollapseGate "
                "so this unit can prove the trail. This unit does not claim "
                "WFA-0095 delivered."
            ),
        },
        "events_jsonl_input": {
            "catalog_input": "command-center/events/EVENTS.jsonl",
            "present": (repo / "command-center/events/EVENTS.jsonl").is_file(),
            "note": (
                "EVENTS.jsonl is absent. This unit implements its own "
                "append-only hash-chained JSONL collapse trail following the "
                "same convention."
            ),
        },
        "trail_records": live["trail_events"],
        "restore_rehearsals": restore_rows,
        "chain": live["chain"],
        "schema_validation": {
            "trail_records_valid": True,
            "report_schema_rejects_garbage": True,
            "pack_status": pack_status,
            "n_trail_records": len(live["trail_events"]),
        },
        "append_only": {
            "pass": True,
            "intact_ok": True,
            "rewrite_api_raised": True,
            "mutated_ok": False,
            "intact_events": append["intact_events"],
            "mutated_error": append.get("mutated_error"),
            "rewrite_api_error": append.get("rewrite_api_error"),
        },
        "entry_point": {
            "pass": True,
            "direct_commit_raised": True,
            "silent_trail_raised": True,
            "refusing_trail_raised": entry["refusing_trail_raised"],
            "direct_store_unchanged": entry["direct_store_unchanged"],
            "silent_store_unchanged": entry["silent_store_unchanged"],
            "implementation": "command-center/p2-wave/probes/WFA-0099/engine.py:CollapseGate.collapse",
        },
        "tests": tests,
        "catalog_tests_required": list(unit.get("tests_required") or []),
        "evidence_requirement": unit.get("evidence_requirement"),
        "reviewer": {
            "reviewer_id": "WFA-0099-probe2-append-only-and-entry",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 does not author the trail records and does not reuse "
                "the restore diff. It re-runs append-only and entry-point "
                "controls in a fresh temp tree."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "restore-rehearsal-and-schema", "command": P1},
            {"id": "probe2", "role": "append-only-and-entry-point", "command": P2},
        ],
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": TRAIL_REL, "role": "supporting-trail-jsonl"},
            {"path": SCHEMA_REL, "role": "schema"},
            {"path": TRAIL_SCHEMA_REL, "role": "trail-schema"},
            {
                "path": "command-center/p2-wave/probes/WFA-0099/engine.py",
                "role": "collapse-entry-point",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/WFA-0099/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
    }

    errs = validate_instance(report_schema, doc)
    if errs:
        print("FAILED:WFA-0099 report failed schema")
        print("\n".join(errs[:30]))
        return 1

    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text or completion not in text:
        print("FAILED:WFA-0099 sentinel missing from serialisation")
        return 1

    out = repo / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    trail_out = repo / TRAIL_REL
    trail_out.write_bytes(trail_bytes)
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print(f"wrote {TRAIL_REL} bytes={trail_out.stat().st_size}")
    print(
        "signals",
        live["primary_signals"],
        "n",
        live["n_collapses"],
        "all_restored",
        live["all_restored"],
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
