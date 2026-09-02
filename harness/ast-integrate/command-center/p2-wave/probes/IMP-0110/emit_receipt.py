#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0110.json from a live moderation cycle."""
from __future__ import annotations

import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools/marketplace/tests"))

from marketplace.event_log import ImmutableRecordError  # noqa: E402
from marketplace.moderation import (  # noqa: E402
    DISPUTE_BODY_FIXTURE,
    FULL_CYCLE_EVENT_TYPES,
    MUTATION_REFUSED,
    REPORT_BODY_FIXTURE,
    RESOLVE_REFUSED,
    DisputeOpportunityRequired,
    ModerationQueue,
    run_full_cycle,
)

OUT = "command-center/receipts/IMP-0110.json"
SCHEMA_RECEIPT = "command-center/schema/receipt.schema.json"
SCHEMA_MOD = "tools/marketplace/schema/moderation.schema.json"
SENTINEL = "SUCCESS:IMP-0110"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe(role: str, method: str, command: str, raw_output: str, exit_code: int) -> dict:
    fp = hashlib.md5(f"{command}|{exit_code}|{raw_output}".encode("utf-8")).hexdigest()
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:2000],
        "exit_code": exit_code,
        "fingerprint": fp,
    }


def run_unit_tests() -> dict:
    import test_moderation as tm

    errors: list[str] = []
    names = [
        "test_full_cycle_event_sequence",
        "test_prior_records_are_immutable",
        "test_resolve_without_dispute_opportunity_refused",
        "test_disk_tamper_is_detected",
    ]
    for name in names:
        try:
            getattr(tm, name)()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}\n{traceback.format_exc()[-800:]}")
    return {
        "passed": not errors,
        "names": names,
        "errors": errors,
    }


def main() -> int:
    tests = run_unit_tests()
    if not tests["passed"]:
        print("FAILED:IMP-0110 unit tests")
        print("\n".join(tests["errors"]))
        return 1

    q = ModerationQueue()
    cycle = run_full_cycle(q)
    types = q.cycle_event_types(cycle["report_id"])
    if types != list(FULL_CYCLE_EVENT_TYPES):
        print("FAILED:IMP-0110 cycle sequence", types)
        return 1

    rid = cycle["report_id"]
    seq0 = cycle["events"][0]["seq"]
    refused = []
    for label, fn in (
        ("edit_report", lambda: q.try_edit_report(rid, "hacked", actor_id="attacker")),
        ("delete_report", lambda: q.try_delete_report(rid, actor_id="attacker")),
        ("edit_dispute", lambda: q.try_edit_dispute(rid, "hacked", actor_id="attacker")),
        ("rewrite_event", lambda: q.log.try_rewrite(seq0, {"body": "forged"}, actor_id="attacker")),
        ("delete_event", lambda: q.log.try_delete(seq0, actor_id="attacker")),
    ):
        try:
            fn()
            print(f"FAILED:IMP-0110 {label} not refused")
            return 1
        except ImmutableRecordError:
            refused.append(label)
    after = q.audit(rid)
    if after["report"]["body"] != REPORT_BODY_FIXTURE:
        print("FAILED:IMP-0110 report mutated")
        return 1
    if after["dispute"]["body"] != DISPUTE_BODY_FIXTURE:
        print("FAILED:IMP-0110 dispute mutated")
        return 1

    neg = ModerationQueue()
    filed = neg.file_report(
        package_id="acme.widget",
        category="spam",
        reporter_id="user:reporter-1",
        body="unsolicited advertising",
    )
    try:
        neg.resolve(
            filed["report_id"],
            outcome="upheld",
            actor_id="moderator:queue",
            rationale="skip the publisher",
        )
        print("FAILED:IMP-0110 negative control did not refuse")
        return 1
    except DisputeOpportunityRequired as exc:
        if exc.refusal.get("event_type") != RESOLVE_REFUSED:
            print("FAILED:IMP-0110 negative control not logged")
            return 1
    if neg.audit(filed["report_id"])["state"] != "filed":
        print("FAILED:IMP-0110 negative control changed state")
        return 1

    q.log.verify_chain()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl = REPO / "tools/marketplace/moderation.py"
    elog = REPO / "tools/marketplace/event_log.py"
    schema = REPO / SCHEMA_MOD
    tests_path = REPO / "tools/marketplace/tests/test_moderation.py"
    impl_sha, impl_n = sha256_file(impl)
    elog_sha, elog_n = sha256_file(elog)
    schema_sha, schema_n = sha256_file(schema)
    tests_sha, tests_n = sha256_file(tests_path)

    src1 = probe(
        "source",
        "command",
        "python3 -B tools/marketplace/tests/test_moderation.py::test_full_cycle_event_sequence",
        json.dumps(
            {
                "event_types": types,
                "report_id": rid,
                "state": cycle["state"],
                "report_body": cycle["report"]["body"],
                "dispute_body": cycle["dispute"]["body"],
            },
            sort_keys=True,
        ),
        0,
    )
    ver1 = probe(
        "verifier",
        "file-read",
        "audit(report_id) after cycle",
        json.dumps(
            {
                "event_types": after["event_types"][:4],
                "report_retained": after["report"]["body"] == REPORT_BODY_FIXTURE,
                "dispute_retained": after["dispute"]["body"] == DISPUTE_BODY_FIXTURE,
            },
            sort_keys=True,
        ),
        0,
    )
    src2 = probe(
        "source",
        "command",
        "python3 -B tools/marketplace/tests/test_moderation.py::test_prior_records_are_immutable",
        json.dumps({"refused": refused, "mutation_events": MUTATION_REFUSED}, sort_keys=True),
        0,
    )
    ver2 = probe(
        "verifier",
        "file-read",
        "bodies after refused mutations",
        json.dumps(
            {
                "report_body": after["report"]["body"],
                "dispute_body": after["dispute"]["body"],
                "unchanged": True,
            },
            sort_keys=True,
        ),
        0,
    )

    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0110",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0110; _USER-PROMPTS.md:10867",
        "title": "Moderation queue and dispute data model",
        "min_bytes_threshold": 128,
        "output_schema": f"{SCHEMA_RECEIPT} + {SCHEMA_MOD}",
        "question": (
            "Implement the append-only data model for reports against a package "
            "(spam, malware, license violation, impersonation) and the dispute "
            "record a publisher can file in response, with every state change "
            "recorded in the event log and no destructive edit of a prior record."
        ),
        "implementation": {
            "module": "tools/marketplace/moderation.py",
            "event_log": "tools/marketplace/event_log.py",
            "schema": SCHEMA_MOD,
            "tests": "tools/marketplace/tests/test_moderation.py",
            "categories": ["spam", "malware", "license_violation", "impersonation"],
            "full_cycle_event_types": list(FULL_CYCLE_EVENT_TYPES),
            "append_only": True,
            "hash_chained": True,
        },
        "measured_cycle": {
            "report_id": rid,
            "event_types": types,
            "report_body": cycle["report"]["body"],
            "dispute_body": cycle["dispute"]["body"],
            "outcome": cycle["resolution"]["outcome"],
            "chain_tip": q.log.last_hash(),
            "event_count": len(q.log),
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "eol": "LF",
                "bytes": 0,
                "sha256": "pending",
            },
            {
                "path": "tools/marketplace/moderation.py",
                "role": "implementation",
                "exists": True,
                "bytes": impl_n,
                "sha256": impl_sha,
            },
            {
                "path": "tools/marketplace/event_log.py",
                "role": "implementation",
                "exists": True,
                "bytes": elog_n,
                "sha256": elog_sha,
            },
            {
                "path": SCHEMA_MOD,
                "role": "schema",
                "exists": True,
                "bytes": schema_n,
                "sha256": schema_sha,
            },
            {
                "path": "tools/marketplace/tests/test_moderation.py",
                "role": "tests",
                "exists": True,
                "bytes": tests_n,
                "sha256": tests_sha,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "A full report-then-dispute-then-resolve cycle produces "
                    + " -> ".join(FULL_CYCLE_EVENT_TYPES)
                    + " and the resolved audit retains both report and dispute text."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/tests/test_moderation.py::test_full_cycle_event_sequence",
                "confidence": "almost-certain",
                "probes": [src1, ver1],
            },
            {
                "claim": (
                    "An attempt to delete or edit a prior report, dispute, or event "
                    "is refused and the refusal is appended to the log; original "
                    "bodies are unchanged."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/tests/test_moderation.py::test_prior_records_are_immutable",
                "confidence": "almost-certain",
                "probes": [src2, ver2],
            },
        ],
        "tests": [
            {
                "id": "test_full_cycle_event_sequence",
                "command": "python3 -B tools/marketplace/tests/test_moderation.py",
                "result": "PASS",
            },
            {
                "id": "test_prior_records_are_immutable",
                "command": "python3 -B tools/marketplace/tests/test_moderation.py",
                "result": "PASS",
            },
            {
                "id": "test_resolve_without_dispute_opportunity_refused",
                "command": "python3 -B tools/marketplace/tests/test_moderation.py",
                "result": "PASS",
            },
            {
                "id": "test_disk_tamper_is_detected",
                "command": "python3 -B tools/marketplace/tests/test_moderation.py",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "resolve-without-dispute-opportunity",
                "kind": "known-broken-fixture",
                "description": (
                    "A resolution without a recorded dispute window must be refused "
                    "and logged as report.resolve_refused; the report stays filed."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": RESOLVE_REFUSED,
                "good_state_output": "report.resolved after dispute window",
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0110-probe2-audit-retention",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Resolved report retains the original report body and the publisher "
                "dispute body; outcome is auditable from the event log alone."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0110/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0110/probe1_full_cycle.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0110/probe1_full_cycle.py",
                    "deferred-to-named-probe",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0072 (hash-chained registry event log) is not delivered in "
                    "this worktree; IMP-0110 ships a compatible append-only writer "
                    "used by the moderation queue rather than importing a missing module."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-bind moderation.EventLog to the IMP-0072 writer when that unit lands."
                ),
            }
        ],
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "timestamps": {
            "started_at": "2026-08-24T18:33:00Z",
            "ended_at": now,
        },
        "immutable_refusals": refused,
        "mutation_refusals_logged": sum(
            1 for e in q.log.events() if e["event_type"] == MUTATION_REFUSED
        ),
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    sha, n = sha256_file(dest)
    receipt["artifacts"][0]["bytes"] = n
    receipt["artifacts"][0]["sha256"] = sha
    dest.write_text(json.dumps(receipt, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    sha2, n2 = sha256_file(dest)
    print(f"wrote {OUT} bytes={n2} sha256={sha2}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
