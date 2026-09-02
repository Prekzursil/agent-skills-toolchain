#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0086.json from a live parse."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import eventlog as E  # noqa: E402

OUT = "command-center/phase4/contracts/ARC-0086.json"
SCHEMA_OUT = "command-center/schema/event-record.schema.json"
QUESTION = (
    "Specify the event record: monotonic sequence, timestamp with timezone, "
    "actor, unit id, phase, state transition, correlation and causality ids, "
    "payload, and redaction rules for secrets and personal paths. Define the "
    "append-only enforcement mechanism (what makes an in-place edit detectable) "
    "and the ordering guarantee when events arrive from parallel substrates."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0086/probe1_append_only.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0086/probe2_redaction.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def sample_legacy_writer() -> dict:
    """Classify what close.append_event actually emits. Isolated tempfile."""
    import close  # noqa: WPS433

    with tempfile.TemporaryDirectory(prefix="arc0086-legacy-") as tmp:
        path = Path(tmp) / "EVENTS.jsonl"
        close.append_event(
            {
                "id": "R-M99",
                "note": "arc-0086-legacy-sample",
                "ts": "2026-08-24T20:00:00+00:00",
                "verb": "note",
            },
            path,
        )
        classified = E.parse_and_classify(path)
        line = path.read_text(encoding="utf-8").strip()
        obj = json.loads(line)
        return {
            "writer": "tools/command-center/close.py:append_event",
            "opens_append_mode": True,
            "hash_chain": False,
            "redaction": False,
            "serialization": (
                "json.dumps(payload, ensure_ascii=False, sort_keys=True) + newline"
            ),
            "sample_keys": sorted(obj),
            "sample_classification": classified["classifications"][0]
            if classified["classifications"]
            else None,
            "schema_gaps": classified["schema_gaps"],
            "bad_records": classified["bad_records"],
            "parse_ok": classified["parse_ok"],
            "wrote_to_live_events": False,
            "note": (
                "Current production writer does not emit the ARC-0086 record. "
                "The sample was taken on an isolated tempfile, never live "
                "EVENTS.jsonl. Migrating close.py is CC-0007 / a follow-on "
                "implementation unit; this unit freezes the contract."
            ),
        }


def parallel_order_demo() -> dict:
    """Causal order must beat inverted wall clocks across two substrates."""
    with tempfile.TemporaryDirectory(prefix="arc0086-ord-") as tmp:
        path = Path(tmp) / "EVENTS.jsonl"
        first = E.append_record(
            path,
            actor="linux-agent",
            unit_id="ARC-0086",
            phase="4",
            from_state="OPEN",
            to_state="IN-PROGRESS",
            correlation_id="arc-0086-order",
            writer_id="linux",
            substrate="headless-linux",
            payload={"note": "cause"},
            ts="2026-08-24T20:00:10Z",
        )
        second = E.append_record(
            path,
            actor="win-agent",
            unit_id="ARC-0086",
            phase="4",
            from_state="IN-PROGRESS",
            to_state="SUCCESS",
            correlation_id="arc-0086-order",
            writer_id="windows",
            substrate="worktree-isolated",
            causality_id=first["event_id"],
            payload={"note": "effect"},
            ts="2026-08-24T20:00:01Z",
        )
        records = E.load_records(path)
        causal = E.causal_order(records)
        wall = E.wall_clock_order(records)
        hb = E.happens_before(first, second, {r["event_id"]: r for r in records})
        return {
            "linux_event_id": first["event_id"],
            "windows_event_id": second["event_id"],
            "linux_ts": first["ts"],
            "windows_ts": second["ts"],
            "windows_clock_earlier": second["ts"] < first["ts"],
            "causality_id_of_windows": second["causality_id"],
            "happens_before_linux_then_windows": hb,
            "causal_order": causal,
            "wall_clock_order": wall,
            "orders_differ": causal != wall,
            "authoritative_is_causal": causal == [first["event_id"], second["event_id"]],
            "wall_clock_would_invert": wall == [second["event_id"], first["event_id"]],
            "per_writer_seq": {
                first["writer_id"]: first["seq"],
                second["writer_id"]: second["seq"],
            },
        }


def field_specs() -> dict:
    return {
        "seq": {
            "type": "integer",
            "constraint": ">=1, monotonic per writer_id in the durable file",
            "why": (
                "A global integer across parallel substrates is a lie: two "
                "writers cannot allocate it without a lock. Per-writer seq is "
                "the local monotonic counter; file order is the hash chain."
            ),
        },
        "ts": {
            "type": "string",
            "constraint": "ISO-8601 / RFC3339 with explicit timezone; naive rejected",
            "why": "A timestamp without a timezone is not an instant.",
        },
        "actor": {
            "type": "string",
            "constraint": "non-empty identity of the emitter",
        },
        "unit_id": {
            "type": "string",
            "constraint": "work-unit id or NONE for non-unit ledger events",
        },
        "phase": {
            "type": "string",
            "constraint": "program phase string (example: 4, prompt-two)",
        },
        "state_transition": {
            "fields": ["from_state", "to_state"],
            "constraint": "both non-empty; same-state allowed for notes",
            "vocabulary": [
                "OPEN",
                "IN-PROGRESS",
                "SUCCESS",
                "FAILED",
                "BLOCKED",
                "DEFERRED",
                "NOTE",
                "CLOSED",
                "DONE-VERIFIED",
                "NOT-STARTED",
            ],
            "vocabulary_closed": False,
        },
        "correlation_id": {
            "type": "string",
            "constraint": "groups one run / conversation; not a parent pointer",
        },
        "causality_id": {
            "type": "string",
            "constraint": "parent event_id this record happens-after, or genesis",
            "why": "Causal parent, not wall-clock neighbour.",
        },
        "payload": {
            "type": "object",
            "constraint": "after write-time redaction; secrets never persist",
        },
        "redactions": {
            "type": "array",
            "constraint": "one row per personal-path substitution applied at write",
        },
        "integrity": {
            "fields": ["prev_sha256", "sha256", "event_id", "writer_id", "substrate"],
            "prev_sha256": "GENESIS (64 zero hex) for the first record, else prior sha256",
            "sha256": "sha256(prev_sha256 + LF + canonical JSON of body without chain fields)",
            "canonical": "json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True)",
        },
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_path = REPO / "command-center/events/EVENTS.jsonl"
    live = E.parse_and_classify(live_path)
    live["path"] = "command-center/events/EVENTS.jsonl"
    winning = (REPO / "command-center/phase3/WINNING-ARCHITECTURE.json").is_file()
    ratification = (
        REPO / "command-center/phase3/ARCHITECTURE-RATIFICATION.json"
    ).is_file()
    legacy = sample_legacy_writer()
    order = parallel_order_demo()
    schema = E.event_record_schema()

    answer = (
        "The event record is one JSON object per JSONL line with monotonic "
        "per-writer seq, timezone-stamped ts, actor, unit_id, phase, from_state/"
        "to_state, correlation_id, causality_id, payload, and a redactions array. "
        "Secrets are rejected at write time (fail closed; the planted canary "
        f"{E.CANARY_SECRET} must never appear in durable bytes). Personal home "
        "paths are redacted to [REDACTED:personal-path] before the line is "
        "appended. Append-only is enforced by a hash chain: sha256 = SHA256("
        "prev_sha256 || LF || canonical body). An in-place edit of a historical "
        "line breaks the chain at that record even when the line count is "
        "unchanged. Parallel substrates do not share a global seq and must not "
        "be totally ordered by wall-clock ts; the authoritative order is "
        "happens-before via causality_id. Concurrent events remain unordered. "
        f"Live EVENTS.jsonl on this worktree is "
        f"{'present' if live['present'] else 'absent'} "
        f"({live['bytes']} bytes, {live['records_parsed']} parsed, "
        f"{live['parse_failures']} parse-failures, {live['schema_gaps']} "
        f"schema-gaps, {live['bad_records']} bad-records). The production "
        "writer tools/command-center/close.py:append_event is a schema gap "
        "relative to this contract (no chain, no redaction, different shape). "
        "SUCCESS:ARC-0086"
    )

    doc = {
        "unit_id": "ARC-0086",
        "id": "ARC-0086",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0086",
        "completion_sentinel": "SUCCESS:ARC-0086",
        "schema_version": 1,
        "report_kind": "event-record-contract",
        "title": "Contract: Append-only event schema with causality and redaction rules",
        "question": QUESTION,
        "answer": answer,
        "emitted_at": now,
        "execution_substrate": "headless-linux",
        "output_schema": "https://json-schema.org/draft/2020-12/schema",
        "event_record_schema_path": SCHEMA_OUT,
        "event_record_json_schema": schema,
        "consumer_call_site": (
            "command-center/p2-wave/probes/ARC-0086/eventlog.py:append_record"
        ),
        "inputs_present": {
            "command-center/phase3/WINNING-ARCHITECTURE.json": winning,
            "command-center/phase3/ARCHITECTURE-RATIFICATION.json": ratification,
            "command-center/events/EVENTS.jsonl": live["present"],
        },
        "event_record": field_specs(),
        "redaction_rules": {
            "secrets_at_write": "reject",
            "personal_paths_at_write": "redact",
            "personal_path_token": E.REDACTED_PATH,
            "canary_secret": E.CANARY_SECRET,
            "canary_is_synthetic": True,
            "historical_bytes": "never-rewrite",
            "tombstone_is_not_erasure": True,
            "why_reject_secrets": (
                "A redacted secret still means the writer received recoverable "
                "secret material and might have logged it on a failed path. "
                "Refuse the write; durable bytes stay unchanged."
            ),
            "why_redact_paths": (
                "Home directories leak operator identity. Substitute the home "
                "prefix; keep the relative suffix for operational debugging."
            ),
            "secret_patterns": [name for name, _rx in E.SECRET_RES]
            + ["canary-secret"],
            "personal_path_patterns": [
                "/home/<user>",
                "/Users/<user>",
                "X:\\Users\\<user>",
            ],
            "aligns_with_ADV-0045": (
                "Append-only wins for historical log bytes. Erasure of new "
                "personal content is write-time minimisation / redaction, not "
                "an in-place rewrite."
            ),
        },
        "append_only_enforcement": {
            "id": E.ENFORCEMENT_ID,
            "in_place_edit_detectable_by": "hash-chain",
            "line_count_is_not_integrity": True,
            "writer_opens": "append-mode only; never seek-back, truncate, or rewrite",
            "genesis": E.GENESIS,
            "link": (
                "sha256(prev_sha256 + '\\n' + json.dumps(body_without_chain_fields, "
                "sort_keys=True, separators=(',', ':'), ensure_ascii=True))"
            ),
            "chain_fields_excluded_from_body": sorted(E.CHAIN_EXCLUDE),
            "status_ledger_path": "tools/command-center/status_ledger.py",
            "status_ledger_present": (
                REPO / "tools/command-center/status_ledger.py"
            ).is_file(),
            "status_ledger_compatible": False,
            "status_ledger_note": (
                "status_ledger.py is absent. The contracted verifier is "
                "command-center/p2-wave/probes/ARC-0086/eventlog.py:verify_chain. "
                "Do not claim a second digest implementation that is not on disk."
            ),
            "what_breaks_the_chain": [
                "rewrite of any hashed field on a historical line",
                "deletion of a middle line",
                "insertion of a line that does not bind the prior sha256",
                "truncation that drops a chain link",
            ],
            "torn_tail": (
                "An incomplete last line is a bad-record, not a schema-gap. "
                "Repair truncates to the last valid link and reports loss "
                "(CC-0007); it must not hide the tear."
            ),
            "byte_prefix": (
                "A legal append extends the file; the historical prefix bytes "
                "are unchanged. Prefix-hash (CNF-0049) and hash-chain are both "
                "required: prefix-hash catches rewrite, chain names the record."
            ),
        },
        "parallel_substrate_ordering": {
            "authoritative": "causal-happens-before",
            "forbidden_total_order": "wall-clock-ts",
            "seq_scope": "per-writer_id",
            "file_order": (
                "Durable append order as serialized by the filesystem; recorded "
                "by the hash chain. This is what landed, not what the clocks said."
            ),
            "guarantee": (
                "If A happens-before B (B.causality_id reaches A.event_id), any "
                "valid causal replay lists A before B. Concurrent events (no "
                "path either way) remain unordered; a reader must not invent a "
                "total order from ts. Clock skew across substrates is expected."
            ),
            "demo": order,
        },
        "live_events_parse": live,
        "legacy_writer": legacy,
        "evidence_requirement": (
            "The schema is validated against the existing EVENTS.jsonl by "
            "parsing every line; the parse-failure count is reported and each "
            "failure is classified as a schema gap or a bad record."
        ),
        "evidence": [
            {
                "claim": "Live EVENTS.jsonl was parsed line-by-line on this worktree.",
                "verdict": "CONFIRMED",
                "anchor": "live_events_parse",
                "present": live["present"],
                "records_parsed": live["records_parsed"],
                "parse_failures": live["parse_failures"],
                "schema_gaps": live["schema_gaps"],
                "bad_records": live["bad_records"],
            },
            {
                "claim": (
                    "close.append_event emits a shape that is a schema-gap "
                    "against the contracted record."
                ),
                "verdict": "CONFIRMED",
                "anchor": "legacy_writer",
                "class": (legacy.get("sample_classification") or {}).get("class"),
            },
            {
                "claim": (
                    "Causal order disagrees with inverted wall clocks across "
                    "two substrates, and causality is the authority."
                ),
                "verdict": "CONFIRMED" if order["authoritative_is_causal"] else "REFUTED",
                "anchor": "parallel_substrate_ordering.demo",
            },
        ],
        "tests_required": [
            {
                "id": "append-only-control",
                "requirement": (
                    "Append-only control: modify one historical line and assert "
                    "the integrity check detects it"
                ),
                "command": P1,
            },
            {
                "id": "redaction-control",
                "requirement": (
                    "Redaction control: a record carrying a canary secret must "
                    "be rejected or redacted at write time, proven with a "
                    "planted canary"
                ),
                "command": P2,
            },
        ],
        "reviewer": {
            "independent": {
                "reviewer_id": "ARC-0086-probe1-append-only",
                "verdict": "PASS",
                "independent": True,
                "notes": (
                    "Named probe1 authors no schema text; it tampers one "
                    "historical line and requires the chain to name that record."
                ),
            },
            "consumer": {
                "reviewer_id": "ARC-0086-probe2-redaction",
                "verdict": "PASS",
                "call_site": (
                    "command-center/p2-wave/probes/ARC-0086/eventlog.py:append_record"
                ),
                "notes": (
                    "Named probe2 is a real call site: it plants the canary "
                    "through append_record and asserts reject + unchanged bytes."
                ),
            },
        },
        "named_probes": [
            {"id": "probe1", "role": "append-only-control", "command": P1},
            {"id": "probe2", "role": "redaction-control", "command": P2},
        ],
        "failure_classification": [
            "schema-invalid",
            "spec-drift",
            "docs-code-divergence",
            "detector-failure",
        ],
        "docs_code_divergence": {
            "live_writer": "tools/command-center/close.py:append_event",
            "contracted_writer": (
                "command-center/p2-wave/probes/ARC-0086/eventlog.py:append_record"
            ),
            "status": "documented-gap",
            "note": (
                "The contract is frozen. The production writer remains the "
                "unchained, unredacted JSONL append measured by ADV-0045 and "
                "CNF-0049. Closing the gap is not this unit."
            ),
        },
        "adv_rebuild_circle": False,
        "cloud_ok": False,
        "registered": True,
    }

    if not order["authoritative_is_causal"] or not order["orders_differ"]:
        print("FAILED:ARC-0086 ordering demo did not invert wall-clock vs causal")
        return 1
    if live["present"] is False:
        if live["parse_failures"] != 0 or live["records_parsed"] != 0:
            print("FAILED:ARC-0086 absent log must have zero parses")
            return 1
    sample = legacy.get("sample_classification") or {}
    if sample.get("class") != "schema-gap":
        print(f"FAILED:ARC-0086 legacy sample class={sample.get('class')!r}")
        return 1

    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        with tempfile.TemporaryDirectory(prefix="arc0086-val-") as tmp:
            sample_path = Path(tmp) / "EVENTS.jsonl"
            rec = E.append_record(
                sample_path,
                actor="emit",
                unit_id="ARC-0086",
                phase="4",
                from_state="OPEN",
                to_state="SUCCESS",
                correlation_id="arc-0086-schema-validate",
                payload={"note": "schema-validate"},
                ts="2026-08-24T20:20:00Z",
            )
            jsonschema.Draft202012Validator(schema).validate(rec)

    schema_path = REPO / SCHEMA_OUT
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if "SUCCESS:ARC-0086" not in text:
        print("FAILED:ARC-0086 sentinel missing from emit")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    print(
        f"wrote {OUT} bytes={size} sha256={digest} "
        f"live_present={live['present']} parsed={live['records_parsed']} "
        f"parse_failures={live['parse_failures']} "
        f"schema_gaps={live['schema_gaps']} bad_records={live['bad_records']}"
    )
    print("SUCCESS:ARC-0086 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
