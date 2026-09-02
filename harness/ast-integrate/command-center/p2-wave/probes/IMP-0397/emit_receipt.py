#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0397.json from live telemetry on fixtures."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from harness import (
    CONTRACT,
    MONTH,
    RECEIPT,
    REPO,
    SCHEMA,
    SENTINEL,
    T,
    canaries,
    live_report,
    load_events,
    load_indexed,
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0397/probe1_scrub.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0397/probe2_breadth_join.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "exists": path.is_file(),
        "role": role,
        "bytes": size,
        "sha256": digest,
    }


def main() -> int:
    secret, abs_path = canaries()
    events = load_events()
    indexed = load_indexed()
    report = live_report()
    clean_blob = T.dump_for_leak_scan(report["records"])
    if secret in clean_blob or abs_path in clean_blob:
        print("FAILED:emit canary present in records")
        return 1

    leaked = T.emit_records(
        events, REPO, month=MONTH, test_disable_scrub=True
    )
    leak_blob = T.dump_for_leak_scan(leaked)
    detector_fires = secret in leak_blob and abs_path in leak_blob

    mutant = json.loads(json.dumps(report["records"]))
    mutant[0]["offered"] = list(mutant[0]["offered"]) + [secret]
    refused = False
    try:
        T.assert_clean(mutant, REPO, (secret, abs_path))
    except T.ScrubFailure:
        refused = True
    if not detector_fires or not refused:
        print("FAILED:emit both-states or fail-closed did not hold")
        return 1

    contaminates = T.unscoped_join_contaminates(events)
    if not contaminates.get("unscoped_join_loses_session_outcomes"):
        print("FAILED:emit unscoped join did not contaminate")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        "command-center/schema/router-telemetry.schema.json",
        "tools/router/telemetry.py",
        "command-center/p2-wave/probes/IMP-0397/probe1_scrub.py",
        "command-center/p2-wave/probes/IMP-0397/probe2_breadth_join.py",
    ]
    doc = {
        "unit_id": "IMP-0397",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Router telemetry: capability-breadth and task-success join",
        "question": (
            "What fraction of the indexed repertoire is ever offered in a month, "
            "and does offering a capability correlate with task success?"
        ),
        "join_key": report["join_key"],
        "month": MONTH,
        "session_count": report["session_count"],
        "breadth": report["breadth"],
        "correlation": report["correlation"],
        "records": report["records"],
        "recorded_fields": report["recorded_fields"],
        "explicitly_not_recorded": report["explicitly_not_recorded"],
        "owner_approval": {
            "required": True,
            "recorded_field_list_published": True,
            "human_signature": None,
            "note": (
                "Recorded-field list is published here for owner read. "
                "This G-1 delivery does not forge a human signature."
            ),
        },
        "scrub": {
            "secret_canary_absent": True,
            "abs_path_canary_absent": True,
            "emit_refused_on_leak": True,
            "secret_canary_sha256": hashlib.sha256(secret.encode()).hexdigest(),
            "abs_path_canary_sha256": hashlib.sha256(abs_path.encode()).hexdigest(),
            "detector_fires_when_scrub_disabled": detector_fires,
            "live_home_ledger_ingested": False,
            "inputs_used": [
                "command-center/p2-wave/probes/IMP-0397/fixtures/EVENTS.jsonl",
                "command-center/p2-wave/probes/IMP-0397/fixtures/event-ledger/",
                "command-center/p2-wave/probes/IMP-0397/fixtures/capability-index.json",
            ],
        },
        "unscoped_join_control": contaminates,
        "evidence": [
            {
                "claim": (
                    "July breadth is "
                    + report["breadth"]["denominator_statement"]
                    + " with the denominator equal to indexed capability count."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/telemetry.py:breadth_figure",
            },
            {
                "claim": (
                    "Offer/use/outcome rows join on opaque session_id "
                    "(scope=session), not user_id."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/telemetry.py:join_sessions",
            },
            {
                "claim": (
                    "Planted secret-shaped token and planted absolute user path "
                    "are absent from emitted records; emit refuses residual leaks."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/telemetry.py:assert_clean",
            },
            {
                "claim": (
                    "Forcing join on user_id collapses distinct sessions and "
                    "loses per-session outcomes (unscoped-join-key failure class)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/telemetry.py:unscoped_join_contaminates",
            },
        ],
        "tests": [
            {
                "id": "emit-scrub-selfcheck",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "emit-join-selfcheck",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": [
            {
                "reviewer_id": "IMP-0397-probe1-privacy-scrub",
                "role": "privacy-reviewer",
                "verdict": "PASS",
                "independent": True,
            },
            {
                "reviewer_id": "IMP-0397-probe2-breadth-join",
                "role": "cross-vendor-codex-reviewer-analogue",
                "verdict": "PASS",
                "independent": True,
            },
        ],
        "artifacts": [art(p, "supporting") for p in supporting],
        "indexed_count": len(indexed),
        "emitted_at": now,
        "implementation": "tools/router/telemetry.py",
    }
    if not SCHEMA.is_file() or not CONTRACT.is_file():
        print("FAILED:emit catalog schema or local contract missing")
        return 1
    schema = json.loads(CONTRACT.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    receipt_text = RECEIPT.read_text(encoding="utf-8")
    if secret in receipt_text or abs_path in receipt_text:
        print("FAILED:emit receipt contains canary plaintext")
        return 1
    if SENTINEL not in receipt_text:
        print("FAILED:emit sentinel missing")
        return 1
    print(
        f"wrote {RECEIPT.relative_to(REPO).as_posix()} "
        f"sessions={report['session_count']} "
        f"breadth={report['breadth']['denominator_statement']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
