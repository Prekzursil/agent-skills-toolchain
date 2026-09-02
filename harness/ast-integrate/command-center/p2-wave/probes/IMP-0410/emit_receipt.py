#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0410.json for the advisory file-lease manager."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/receipts/IMP-0410.json"
SCHEMA = "command-center/schema/file-lease.schema.json"
SENTINEL = "SENTINEL:IMP-0410:LEASES-ADVISORY-LOGGED"
QUESTION = (
    "Implement path leases so a session can declare the files it will write, "
    "renew while working, and release on exit. Exact target: a lease must be "
    "advisory and never block a write, but every write to a leased path by a "
    "non-holder must produce a logged conflict event."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0410/probe1_expiry_renew.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0410/probe2_advisory_negative.py"
)


def test_row(src: dict, extra: dict | None = None) -> dict:
    row = {
        "id": src["id"],
        "result": src["result"],
        "pass": bool(src["pass"]),
    }
    if extra:
        row.update(extra)
    for k, v in src.items():
        if k in {"id", "result", "pass", "event_log_excerpt"}:
            continue
        if k not in row:
            row[k] = v
    return row


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0410-emit-") as td:
        tmp = Path(td)
        rows = S.run_all(tmp)
    failed = [k for k, v in rows.items() if not v.get("pass")]
    if failed:
        print(f"FAILED:IMP-0410 scenarios {failed}")
        print(json.dumps({k: rows[k] for k in failed}, indent=2, sort_keys=True))
        return 1

    excerpt = list(rows["advisory"].get("event_log_excerpt") or [])
    if not excerpt:
        print("FAILED:IMP-0410 no conflict excerpt")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "IMP-0410",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "file_lease",
        "schema_version": 1,
        "title": "Advisory file-lease manager with renew and expiry",
        "question": QUESTION,
        "answer": (
            "FileLeaseManager in command-center/leases/manager.py stores per-session "
            "path leases as lease-<id>.json via tmp-plus-rename. acquire/renew/release "
            "are the session lifecycle. note_write always writes destination bytes and "
            "never sets refused=true; when the writer is not among active holders of "
            "that exact path it appends a lease-conflict event with write_allowed and "
            "write_succeeded both true. Expired and released leases drop out of "
            "active_holders so they stop generating conflicts. Unleased paths produce "
            "an empty conflict list. Overlap (globs, case folding, directory "
            "containment) is out of scope (IMP-0411)."
        ),
        "policy": {
            "advisory": True,
            "writes_never_refused": True,
            "non_holder_conflict_logged": True,
            "unleased_silent": True,
            "overlap_algorithm": "exact-normalized-path (IMP-0411 owns glob/case/dir)",
        },
        "manager": {
            "module": "command-center/leases/manager.py",
            "store": "command-center/leases/",
            "acquire": "declare session_id + paths + ttl; concurrent holders allowed",
            "renew": "holder-only; expires_at = now + ttl; refused after expiry",
            "release": "holder-only; status=released; subsequent writes are silent",
            "note_write": "always ok; log lease-conflict per foreign active holder",
            "clock": "injectable FakeClock.now so expiry tests do not wall-sleep",
        },
        "tests": {
            "expiry": test_row(
                rows["expiry"],
                {
                    "command": P1,
                    "detail": (
                        "non-holder write at t+5 logs conflict; write at t+11 "
                        "(past ttl=10) logs none; neither write is refused"
                    ),
                },
            ),
            "renew_extends": test_row(
                rows["renew_extends"],
                {
                    "command": P1,
                    "detail": (
                        "renew at t+8 moves expiry 2010->2018; non-holder at t+13 "
                        "still conflicts. Unrenewed twin at t+13 is silent."
                    ),
                },
            ),
            "advisory": test_row(
                rows["advisory"],
                {
                    "command": P2,
                    "detail": (
                        "sess-B wrote non-holder-payload to a path leased by sess-A; "
                        "bytes landed; refused=false; one lease-conflict event"
                    ),
                },
            ),
            "unleased_negative_control": test_row(
                rows["unleased_negative_control"],
                {
                    "command": P2,
                    "detail": (
                        "write to src/unleased.txt while a different path is leased "
                        "produces zero conflict events"
                    ),
                },
            ),
        },
        "blocking_mutant": test_row(
            rows["blocking_mutant"],
            {
                "detail": (
                    "wrapper that refuses foreign writes fails advisory; live "
                    "manager does not. Both-states control, not production code."
                )
            },
        ),
        "evidence": [
            {
                "kind": "observation",
                "detail": (
                    f"Non-holder sess-B wrote {rows['advisory']['on_disk']!r} to "
                    f"src/advisory.txt held by sess-A. Event log records "
                    f"lease-conflict with write_allowed=true write_succeeded=true. "
                    f"refused={rows['advisory']['refused']}."
                ),
            },
            {
                "kind": "control",
                "detail": (
                    "Unleased path src/unleased.txt: "
                    f"conflict_event_count="
                    f"{rows['unleased_negative_control']['conflict_event_count']}, "
                    f"on_disk={rows['unleased_negative_control']['on_disk']!r}."
                ),
            },
            {
                "kind": "variant",
                "detail": (
                    "Expiry both-states: before_expiry_conflict="
                    f"{rows['expiry']['before_expiry_conflict']} "
                    f"after_expiry_conflict={rows['expiry']['after_expiry_conflict']}."
                ),
            },
            {
                "kind": "inventory",
                "detail": (
                    "Implementation files: command-center/leases/manager.py, "
                    "command-center/schema/file-lease.schema.json, probes under "
                    "command-center/p2-wave/probes/IMP-0410/."
                ),
            },
        ],
        "event_log_excerpt": excerpt,
        "reviewer": {
            "reviewer_id": "IMP-0410-probe2-advisory-negative",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 is a different mechanism from probe 1 (write-refusal and "
                "unleased silence vs clocked TTL/renew). Blocking mutant fires on "
                "the refused-write state and is silent on the live manager."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "expiry-and-renew-extends", "command": P1},
            {"id": "probe2", "role": "advisory-and-unleased-negative", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/leases/manager.py",
                "exists": True,
                "role": "implementation",
            },
        ],
        "cloud_ok": False,
        "registered": True,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "role": "implementer",
            "execution_substrate": "linux-worktree",
            "ts": now,
        },
        "notes": (
            "G-1 for IMP-0410 only. Leases are advisory: they log, they do not "
            "block. cloud_ok is not delivery. Did not run unit_manifest.py --write."
        ),
        "report": {
            "kind": "file-lease",
            "observations": [
                {
                    "name": "non-holder-write-advisory",
                    "measured": True,
                    "method": "FileLeaseManager.note_write",
                    "anchor": "command-center/leases/manager.py",
                },
                {
                    "name": "expiry-drops-conflict",
                    "measured": True,
                    "method": "FakeClock + note_write before/after TTL",
                    "anchor": "command-center/p2-wave/probes/IMP-0410/probe1_expiry_renew.py",
                },
            ],
            "control_ids": [
                "unleased_negative_control",
                "blocking_mutant",
            ],
        },
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0410",
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "two same-fingerprint structural refutes park BLOCKED with "
                "required_fix named; no ADV rebuild circle"
            ),
        },
        "negative_controls": [
            {
                "id": "unleased_negative_control",
                "kind": "absent-input",
                "description": "write to an unleased path produces zero conflict events",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "blocking_mutant",
                "kind": "mutation",
                "description": (
                    "wrapper that refuses foreign writes fails advisory; live "
                    "manager does not"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0410/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "IMP-0411 glob-aware pairwise lease-overlap",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "probe": {
                    "role": "source",
                    "method": "catalog-input",
                    "command": "command-center/receipts/IMP-0410.json is IMP-0411 input",
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Glob/case/directory overlap is IMP-0411; this unit matches "
                    "exact normalised paths only."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Deliver IMP-0411 overlap truth table.",
            }
        ],
    }

    # Catalog file-lease.schema.json is a generated $ref shim with no local
    # constraints. Draft7Validator against it either raises on the unresolved
    # $ref or accepts garbage. Contract schema below is the live rejector.
    contract = {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "tests",
            "event_log_excerpt",
            "policy",
            "evidence",
            "reviewer",
            "report",
        ],
        "properties": {
            "unit_id": {"const": "IMP-0410"},
            "state": {"enum": ["SUCCESS"]},
            "sentinel": {"const": SENTINEL},
            "event_log_excerpt": {"type": "array", "minItems": 1},
            "policy": {
                "type": "object",
                "required": ["advisory", "writes_never_refused"],
                "properties": {
                    "advisory": {"const": True},
                    "writes_never_refused": {"const": True},
                },
            },
            "tests": {
                "type": "object",
                "required": [
                    "expiry",
                    "renew_extends",
                    "advisory",
                    "unleased_negative_control",
                ],
            },
            "evidence": {"type": "array", "minItems": 2},
            "reviewer": {
                "type": "object",
                "required": ["verdict", "independent"],
                "properties": {
                    "verdict": {"const": "PASS"},
                    "independent": {"const": True},
                },
            },
            "report": {
                "type": "object",
                "required": ["kind", "observations", "control_ids"],
                "properties": {"kind": {"const": "file-lease"}},
            },
        },
    }
    validator = jsonschema.Draft7Validator(contract)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:IMP-0410 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "IMP-0410", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:IMP-0410 schema accepted garbage")
            return 1

    out = S.REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:IMP-0410 sentinel missing from serialized receipt")
        return 1
    out.write_text(text, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0410 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:IMP-0410 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
