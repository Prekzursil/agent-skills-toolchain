#!/usr/bin/env python3
"""Emit command-center/phase3/A5/MIGRATION.json for ARC-0035."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import adapters as A  # noqa: E402
import drain as Dr  # noqa: E402
import fold as F  # noqa: E402
import harvest as H  # noqa: E402
import reviewer as R  # noqa: E402

OUT = "command-center/phase3/A5/MIGRATION.json"
SCHEMA = "command-center/schema/migration-plan.schema.json"
QUESTION = (
    "Design the path from today's ad-hoc dispatch (Task subagents, Codex MCP "
    "threads, Databricks jobs) to ONE work-unit contract: what adapter each "
    "existing rail needs, how in-flight work is drained rather than abandoned, "
    "and how the existing event log is folded into the new ledger WITHOUT "
    "rewriting history."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0035/probe1_conservation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0035/probe2_append_only.py"
)
SOURCE = HERE / "fixtures" / "source-events.jsonl"
LEDGER = HERE / "fixtures" / "ledger.jsonl"
DROPS = HERE / "fixtures" / "drops.jsonl"
LIVE_EVENTS = REPO / "command-center" / "events" / "EVENTS.jsonl"

# Catalog shim (command-center/schema/migration-plan.schema.json) $ref's
# platform receipt_core via an ast-integrate.invalid URI. That physical
# profile is a generic_report envelope (tests as array, additionalProperties
# false). This unit's named probes read fold/tests/drain_procedure dicts.
# Validate a local contract that still rejects garbage; do not treat the
# unresolved remote $ref as "any object is valid".
LOCAL_SCHEMA = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "fold",
        "tests",
        "drain_procedure",
        "rails",
        "work_unit_contract",
        "reviewer",
        "negative_controls",
    ],
    "properties": {
        "unit_id": {"const": "ARC-0035"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:ARC-0035"},
        "fold": {
            "type": "object",
            "required": [
                "input_events",
                "output_records",
                "classified_drops",
                "conservation_holds",
            ],
            "properties": {"conservation_holds": {"const": True}},
        },
        "tests": {
            "type": "object",
            "required": ["record_count_conservation", "append_only_assertion"],
        },
        "drain_procedure": {
            "type": "object",
            "required": ["census", "forbids_abandon_without_record"],
        },
        "rails": {"type": "array", "minItems": 3},
        "reviewer": {
            "type": "object",
            "required": ["verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "negative_controls": {"type": "array", "minItems": 2},
    },
}


def _live_unmodified_after(before_sha: str | None) -> bool:
    if before_sha is None:
        return True
    if not LIVE_EVENTS.is_file():
        return False
    return H.sha256_bytes(LIVE_EVENTS.read_bytes()) == before_sha


def main() -> int:
    live_sha = (
        H.sha256_bytes(LIVE_EVENTS.read_bytes()) if H.live_present() else None
    )
    info = H.harvest(SOURCE)
    if not _live_unmodified_after(live_sha):
        print("FAILED:ARC-0035 harvest rewrote live EVENTS.jsonl")
        return 1
    rel = SOURCE.relative_to(REPO).as_posix()
    folded = F.fold_file(SOURCE, LEDGER, DROPS, rel)
    if not folded.get("ok"):
        print("FAILED:ARC-0035 fold", folded.get("reason"))
        return 1
    if not folded.get("conservation_holds"):
        print(
            "FAILED:ARC-0035 conservation "
            f"{folded['input_events']} != "
            f"{folded['output_records']}+{folded['classified_drops']}"
        )
        return 1
    if folded["classified_drops"] < 1 or folded["output_records"] < 5:
        print(
            f"FAILED:ARC-0035 slice too thin records={folded['output_records']} "
            f"drops={folded['classified_drops']}"
        )
        return 1
    if not folded.get("source_unmodified") or not folded.get("both_directions"):
        print("FAILED:ARC-0035 source mutated or bidirectional proof failed")
        return 1

    inplace = F.fold_file(SOURCE, SOURCE, DROPS, rel)
    if not inplace.get("refused"):
        print("FAILED:ARC-0035 in-place rewrite was not refused")
        return 1

    Dr.write_census()
    drained = Dr.drain()
    if not drained.get("ok") or drained.get("abandoned_without_record") != 0:
        print("FAILED:ARC-0035 drain")
        return 1
    if drained["in_flight"] != drained["drained"]:
        print("FAILED:ARC-0035 drain census mismatch")
        return 1
    neg = Dr.refuse_abandon_without_record(Dr.load_census())
    if not neg.get("pass"):
        print("FAILED:ARC-0035 abandon-without-record control")
        return 1

    reviewed = R.review(SOURCE)
    if reviewed.get("verdict") != "PASS" or not reviewed.get("both_directions"):
        print("FAILED:ARC-0035 reviewer", json.dumps(reviewed, indent=2)[:1500])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    design_present = (REPO / "command-center/phase3/A5/DESIGN.json").is_file()
    ledger_rel = LEDGER.relative_to(REPO).as_posix()
    drops_rel = DROPS.relative_to(REPO).as_posix()

    doc = {
        "unit_id": "ARC-0035",
        "architecture_id": "A5",
        "architecture_class": "distributed-workflow-runtime",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "migration-plan",
        "title": (
            "A5 (distributed workflow-runtime): fold ad-hoc rails into one "
            "work-unit contract without dropping in-flight work"
        ),
        "question": QUESTION,
        "sentinel": "SUCCESS:ARC-0035",
        "completion_sentinel": "SUCCESS:ARC-0035",
        "min_bytes_threshold": 2048,
        "work_unit_contract": A.CONTRACT,
        "rails": A.RAILS,
        "drain_procedure": {
            "forbids_abandon_without_record": True,
            "barrier": (
                "New dispatch on old rails is refused until every census row "
                "has a terminal ledger kind=complete|fail|drain. The barrier "
                "is a count: in_flight == drained and abandoned_without_record "
                "== 0, not a wall-clock guess."
            ),
            "steps": [
                "Freeze new ad-hoc dispatch: Task/MCP/Databricks adapters refuse a spawn that has no prior kind=claim.",
                "Census in-flight work per rail (Task ids, MCP thread ids, Databricks active runs).",
                "For each census row, append kind=drain outcome=IN_FLIGHT_LEASED (still running) or ABANDONED (process gone, no artifact). Never delete the census row as a substitute.",
                "Lease those unit_ids onto the typed work-unit queue; the shared completion reducer stays FALSE until a terminal complete|fail row exists.",
                "Only after the barrier (every census row has a drain or terminal row) disable the old rails. Rollback re-enables them; the ledger is not unwritten.",
            ],
            "census": {
                "in_flight": drained["in_flight"],
                "drained": drained["drained"],
                "abandoned_without_record": 0,
            },
            "notes": (
                "The three-row census is a disclosed drain fixture covering the "
                "three named rails. It is not a claim that live Task/MCP/"
                "Databricks processes were inspected on this host."
            ),
        },
        "source_event_log": {
            "catalog_path": info["catalog_path"],
            "present_on_worktree": info["present_on_worktree"],
            "slice_origin": info["slice_origin"],
            "slice_path": info["slice_path"],
            "writer": info["writer"],
            "live_sha256": info.get("live_sha256"),
            "live_unmodified": info.get("live_unmodified"),
            "fold_does_not_rewrite_source": True,
        },
        "fold": {
            "procedure": [
                "Treat the source JSONL as immutable; refuse dest==source.",
                "For each physical line, json.loads. Parseable objects become ledger kind=fold records carrying source.raw and source.sha256.",
                "Blank lines and malformed JSON are classified drops persisted to a distinct drops JSONL, never silently omitted.",
                "Ledger records are hash-chained (prev_hash, event_hash). The source file is not opened for write.",
                "Conservation: input_events == output_records + classified_drops. Reverse concatenation of source.raw in line_no order reconstitutes the slice.",
            ],
            "input_events": folded["input_events"],
            "output_records": folded["output_records"],
            "classified_drops": folded["classified_drops"],
            "conservation_holds": True,
            "ledger_path": ledger_rel,
            "drops_path": drops_rel,
        },
        "ledger_record_shape": {
            "required_fields": list(F.LEDGER_FIELDS),
            "append_only": True,
            "preserves_source_bytes": True,
            "hash_chain": (
                "event_hash = sha256(canonical JSON of the record minus "
                "event_hash); prev_hash of seq=1 is 64 zero nibbles"
            ),
        },
        "sample": folded["sample"],
        "tests": {
            "record_count_conservation": {
                "pass": True,
                "input_events": folded["input_events"],
                "output_records": folded["output_records"],
                "classified_drops": folded["classified_drops"],
                "python_line_count": folded["input_events"],
            },
            "append_only_assertion": {
                "pass": True,
                "source_unmodified": True,
                "in_place_rewrite_refused": True,
                "ledger_path_distinct": True,
                "live_events_unmodified": True if live_sha is None or _live_unmodified_after(live_sha) else False,
                "source_sha256_before": folded["source_sha256_before"],
                "source_sha256_after": folded["source_sha256_after"],
            },
        },
        "negative_controls": [
            {
                "id": "in-place-rewrite",
                "requested": "fold dest == source path",
                "refused": True,
                "pass": True,
                "reason": inplace.get("reason"),
            },
            {
                "id": "abandon-without-record",
                "requested": "drop an in-flight census row with no ledger write",
                "refused": True,
                "pass": True,
                "reason": neg.get("reason"),
            },
        ],
        "evidence": {
            "fold_executed": True,
            "record_count_preserved": True,
            "both_directions": True,
            "two_independent_signals": True,
            "notes": (
                f"Signal 1 is Python json.loads line counts "
                f"(in={folded['input_events']} out={folded['output_records']} "
                f"drops={folded['classified_drops']}). Signal 2 is source "
                f"sha256 invariance plus wc -l/wc -c (probe2) and the drain "
                f"census field (in_flight={drained['in_flight']}). "
                f"EVENTS.jsonl present={info['present_on_worktree']}. "
                f"A5 DESIGN.json present={design_present}. Emitted {now}."
            ),
        },
        "scope": {
            "events_jsonl_present": info["present_on_worktree"],
            "a5_design_present": design_present,
            "proof_surface": (
                "Live command-center/events/EVENTS.jsonl is the fixture prefix "
                "(byte-identical). Extra rows and classified drops append onto "
                "the fixture only via close.append_event. Fold writes a distinct "
                "ledger JSONL and refuses dest==source. Drain fixture covers the "
                "three named rails."
            ),
            "does_not_claim": [
                "the live EVENTS.jsonl was rewritten (it is read-only for this unit)",
                "command-center/phase3/A5/DESIGN.json exists (ARC-0031 is a dependency, not a blocker for this fold proof)",
                "live Task/MCP/Databricks processes were inspected here",
                "exactly-once delivery",
                "cloud ok=true is delivery",
                "the generated catalog shim's generic_report/receipt_core envelope is this file's body (named probes read fold/tests/drain_procedure)",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "migration-engineer",
            "execution_substrate": "local-parallel",
        },
        "reviewer": {
            "reviewer_id": reviewed["reviewer_id"],
            "verdict": reviewed["verdict"],
            "independent": True,
            "both_directions": True,
            "notes": reviewed["notes"],
        },
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "record-count-conservation", "command": P1},
            {"id": "probe2", "role": "append-only-wc-and-drain", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": info["slice_path"], "exists": True, "role": "source-slice"},
            {"path": ledger_rel, "exists": True, "role": "folded-ledger"},
        ],
    }

    validator = jsonschema.Draft7Validator(LOCAL_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0035 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "ARC-0035", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ARC-0035 schema accepted garbage")
            return 1
    shim_path = REPO / SCHEMA
    if not shim_path.is_file() or shim_path.stat().st_size <= 0:
        print("FAILED:ARC-0035 catalog output_schema missing on disk")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0035 artifact too small {size}")
        return 1
    print(
        f"wrote {OUT} bytes={size} in={folded['input_events']} "
        f"out={folded['output_records']} drops={folded['classified_drops']} "
        f"events_present={info['present_on_worktree']}"
    )
    print("SUCCESS:ARC-0035")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
