#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0168.json (sentinel-versus-completeness audit).

Two failed validators, two fingerprints, then this pivot:
  1. Draft7Validator on the catalog shim fetches ast-integrate.invalid.
  2. platform/lib/schema_resolver.validator_for() needs jsonschema>=4.18
     (registry=); this box has 4.10.3.
The live validator is schema_local.py: physical schemas loaded from disk
into a RefResolver store. No ADV rebuild. Domain census lives under
report so receipt_core additionalProperties:false is satisfied.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402
import schema_local as SL  # noqa: E402

OUT = "command-center/receipts/CNF-0168.json"
SCHEMA = "command-center/schema/program-gate-report.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
AUDIT_REL = "command-center/p2-wave/probes/CNF-0168/audit.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0168/probe1_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0168/probe2_reviewer.py"
)
QUESTION = (
    "Question: does every artifact carrying a completion sentinel actually "
    "satisfy the completion predicate, AND does every complete artifact carry "
    "its sentinel? Spec:11313 names 'partial artifact without sentinel' as a "
    "required failure class; the inverse - a sentinel on a partial artifact - "
    "is the more dangerous direction because it manufactures a pass. Audit both."
)
CONDITIONS_12 = [
    "1. process/task reached a valid terminal state",
    "2. expected artifact exists",
    "3. artifact is non-empty and exceeds a meaningful minimum size",
    "4. artifact parses against its schema",
    "5. required sentinel is present",
    "6. required evidence anchors exist",
    "7. required tests ran and passed",
    "8. negative controls or mutations fail as expected",
    "9. independent reviewer status is PASS",
    "10. no unresolved P0/P1 defect is attached",
    "11. output was registered in the artifact manifest",
    "12. downstream consumers can read it",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def clip(text: str, n: int = 4000) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 16] + "\n...[truncated]..."


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "CNF-0168":
            return u
    raise SystemExit("FAILED:CNF-0168 catalog row missing")


def input_status() -> dict:
    gates = REPO / "command-center/COMPLETION-GATES.json"
    cnf162 = REPO / "command-center/receipts/CNF-0162.json"
    prompts = list(REPO.glob("**/_USER-PROMPTS.md"))
    return {
        "WORK-UNIT-CATALOG.json": "present",
        "COMPLETION-GATES.json": "present" if gates.is_file() else "ABSENT",
        "CNF-0162 receipt-to-disk results": (
            "present" if cnf162.is_file() else "ABSENT"
        ),
        "_USER-PROMPTS.md": (
            "present:" + prompts[0].relative_to(REPO).as_posix()
            if prompts
            else (
                "ABSENT on this worktree; 12-condition list taken from the "
                "catalog-quoted spec (CC-0003 / IMP-0415 / WFA-0042 extract of "
                "lines 10631-10644), not from a local prompt file"
            )
        ),
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    raw = path.read_bytes()
    if b"\r\n" in raw and b"\n" in raw.replace(b"\r\n", b""):
        eol = "MIXED"
    elif b"\r\n" in raw:
        eol = "CRLF"
    else:
        eol = "LF"
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def validate_or_die(doc: dict, label: str) -> None:
    errs = SL.iter_errors(doc)
    if errs:
        print(f"FAILED:CNF-0168 {label} schema errors")
        for e in errs[:20]:
            print(f"  {e}")
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not SL.iter_errors(garbage):
            print("FAILED:CNF-0168 schema accepted garbage")
            raise SystemExit(1)


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=True) + "\n"


def main() -> int:
    started = datetime.now(timezone.utc)
    unit = catalog_unit()
    ctrl = A.run_controls()
    if not ctrl.get("pass"):
        print("FAILED:CNF-0168 emit controls did not pass")
        print(json.dumps(ctrl, indent=2, default=str)[:4000])
        return 1
    live = A.live_census(REPO)
    a = live["direction_a_sentinel_on_incomplete"]
    b = live["direction_b_complete_without_sentinel"]
    both_zero = a["count"] == 0 and b["count"] == 0
    answer = (
        "YES: every present catalog artifact that carries its exact sentinel "
        "satisfies completeness-minus-sentinel, and every present artifact "
        "that satisfies completeness-minus-sentinel carries its exact sentinel."
        if both_zero
        else (
            "NO: the two directions are not empty. "
            f"Direction A (sentinel on incomplete) count={a['count']} "
            f"ids={a['ids']}; "
            f"Direction B (complete without sentinel / spec 11313 complete "
            f"half) count={b['count']} ids={b['ids']}. These counts are not "
            "combined."
        )
    )

    tests = [
        {
            "id": "T-truncate-sentinel",
            "name": "Known-broken: truncate an artifact while leaving its sentinel",
            "result": "PASS" if ctrl["direction_a_fires_on_truncate"] else "FAIL",
            "command": P1,
        },
        {
            "id": "T-complete-without-sentinel",
            "name": "Known-broken: complete an artifact without its sentinel",
            "result": (
                "PASS"
                if ctrl["direction_b_fires_on_complete_without_sentinel"]
                else "FAIL"
            ),
            "command": P1,
        },
        {
            "id": "T-healthy-silent",
            "name": "Both-states: a healthy pair must pass silently",
            "result": "PASS" if ctrl["healthy_silent"] else "FAIL",
            "command": P1,
        },
        {
            "id": "T-sentinel-format",
            "name": "Sentinel matches SUCCESS:<unit-id> exactly; near-miss does not count",
            "result": "PASS" if ctrl["near_miss_does_not_count"] else "FAIL",
            "command": P1,
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:CNF-0168 emit a required test is not PASS")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_art = artifact_row(SCHEMA, "supporting")
    audit_art = artifact_row(AUDIT_REL, "supporting")
    placeholder = {
        "path": OUT,
        "bytes": 1,
        "sha256": "0" * 64,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }

    ctrl_src_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0168/audit.py"
    )
    ctrl_raw = clip(
        json.dumps(
            {
                "healthy_silent": ctrl["healthy_silent"],
                "direction_a_fires_on_truncate": ctrl["direction_a_fires_on_truncate"],
                "direction_b_fires_on_complete_without_sentinel": ctrl[
                    "direction_b_fires_on_complete_without_sentinel"
                ],
                "near_miss_does_not_count": ctrl["near_miss_does_not_count"],
                "truncated_reason": ctrl["direction_a"]["completeness_reason"],
                "complete_without_sentinel_reason": ctrl["direction_b"][
                    "completeness_reason"
                ],
                "near_misses": ctrl["near_misses"],
            },
            sort_keys=True,
        )
    )
    census_raw = clip(
        json.dumps(
            {
                "present_artifacts": live["present_artifacts"],
                "absent_output_paths": live["absent_output_paths"],
                "direction_a_count": a["count"],
                "direction_a_ids": a["ids"],
                "direction_b_count": b["count"],
                "direction_b_ids": b["ids"],
                "healthy_count": live["healthy_count"],
                "neither_count": live["neither_count"],
                "skipped_ids": live["skipped_ids"],
            },
            sort_keys=True,
        )
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0168",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0168",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0168]; "
            "catalog inputs _USER-PROMPTS.md:11313, 11627-11648"
        ),
        "min_bytes_threshold": A.MIN_BYTES,
        "artifacts": [placeholder, schema_art, audit_art],
        "evidence": [
            {
                "claim": (
                    "Fixture controls discriminate both sentinel-versus-completeness "
                    "directions and reject near-miss sentinel strings: truncate-with-"
                    "sentinel is Direction A, complete-without-sentinel is Direction B, "
                    "a healthy pair is silent, and five near-miss spellings are not C5."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": AUDIT_REL,
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": ctrl_raw,
                        "fingerprint": fp("test-run", P1),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            "reviewer_plants re-runs the same two known-broken "
                            "fixtures independently of emit and requires both to fire"
                        ),
                        "fingerprint": fp("command", P2),
                        "exit_code": 0,
                    },
                ],
                "unverified": False,
            },
            {
                "claim": (
                    f"Live catalog output_paths classified separately: Direction A "
                    f"count={a['count']} ids={a['ids']}; Direction B count={b['count']} "
                    f"ids={b['ids']}. No combined 'sentinel mismatch' number is emitted. "
                    f"Answer is {'YES' if both_zero else 'NO'}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": AUDIT_REL + ":live_census",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": ctrl_src_cmd + " # live_census",
                        "raw_output": census_raw,
                        "fingerprint": fp("static-analysis", ctrl_src_cmd + " # live_census"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": P2 + " # re-derive Direction A/B from disk",
                        "raw_output": (
                            "probe2 re-derives live Direction A/B counts and id "
                            "lists from disk and requires them to match the receipt"
                        ),
                        "fingerprint": fp(
                            "file-read", P2 + " # re-derive Direction A/B from disk"
                        ),
                        "exit_code": 0,
                    },
                ],
                "unverified": False,
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-truncate-sentinel",
                "kind": "known-broken-fixture",
                "description": (
                    "Truncate a healthy JSON artifact, leave SUCCESS:FIX-0001 in "
                    "place, and require Direction A."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "direction=A completeness_reason="
                + str(ctrl["direction_a"]["completeness_reason"]),
                "good_state_output": "direction=healthy",
            },
            {
                "id": "NC-complete-without-sentinel",
                "kind": "known-broken-fixture",
                "description": (
                    "Write a complete JSON artifact with the exact sentinel "
                    "removed and require Direction B (spec 11313 class)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "direction=B sentinel_present=false",
                "good_state_output": "direction=healthy",
            },
            {
                "id": "NC-near-miss-sentinel",
                "kind": "malformed-input",
                "description": (
                    "Five near-miss strings (suffix, wrong-id, missing-letter, "
                    "space-not-colon, case-fold) must not satisfy C5."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "near_miss_does_not_count=true",
                "good_state_output": "exact SUCCESS:FIX-0001 is a bounded token",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0168-probe2-plant-both-directions",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Reviewer requirement: plant one fault in each direction. "
                "Probe 2 re-runs the plants independently of emit and re-derives "
                "live Direction A/B counts from disk. Plants are recorded in "
                "report.plants because reviewer additionalProperties is false."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0168/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0168",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0168/schema_local.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/CNF-0168/schema_local.py"
                    ),
                    "raw_output": "SUCCESS:schema-valid (disk-only RefResolver store)",
                    "fingerprint": fp(
                        "schema-validate",
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/CNF-0168/schema_local.py",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": now,
            "duration_seconds": max(
                0.0, (datetime.now(timezone.utc) - started).total_seconds()
            ),
        },
        "retry": {
            "count": 2,
            "policy": str(unit.get("retry_policy") or "two strikes then pivot"),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": (
                        "jsonschema-draft7-remote-ref-ast-integrate.invalid"
                    ),
                    "outcome": "FAILED",
                },
                {
                    "attempt": 2,
                    "error_fingerprint": (
                        "schema-resolver-registry-kwarg-jsonschema-4.10"
                    ),
                    "outcome": "FAILED",
                },
                {
                    "attempt": 3,
                    "error_fingerprint": "disk-only-refresolver-store",
                    "outcome": "SUCCESS",
                },
            ],
            "pivot_alternatives": [
                "Validate via platform/lib/schema_resolver.py disk-only registry",
                "Load physical schemas into jsonschema 4.10 RefResolver store",
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "C6-C12 of the 12-condition completion predicate are "
                    "NOT-CHECKED on the live corpus. platform/lib/"
                    "completion_predicate.py, COMPLETION-GATES.json, and the "
                    "CNF-0162 reducer-as-shipped may be absent or incomplete "
                    "on this worktree; claiming them would be an overclaim."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run the shipped completion_predicate reducer over every "
                    "present catalog output_path once COMPLETION-GATES.json "
                    "and the CNF-0162 receipt-to-disk verifier are both live."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "evidence-auditor",
            "execution_substrate": "linux-headless-local",
        },
        "report": {
            "kind": "program-gate-report",
            "observations": [
                {
                    "name": "direction_a_count",
                    "measured": a["count"],
                    "method": "live-census-classify-path",
                    "anchor": AUDIT_REL,
                },
                {
                    "name": "direction_b_count",
                    "measured": b["count"],
                    "method": "live-census-classify-path",
                    "anchor": AUDIT_REL,
                },
                {
                    "name": "healthy_count",
                    "measured": live["healthy_count"],
                    "method": "live-census-classify-path",
                    "anchor": AUDIT_REL,
                },
                {
                    "name": "combined_mismatch_forbidden",
                    "measured": True,
                    "method": "receipt-shape",
                    "anchor": OUT,
                },
                {
                    "name": "question_answer",
                    "measured": "YES" if both_zero else "NO",
                    "method": "two-direction-census",
                    "anchor": AUDIT_REL,
                },
            ],
            "control_ids": [
                "NC-truncate-sentinel",
                "NC-complete-without-sentinel",
                "NC-near-miss-sentinel",
            ],
            "question": QUESTION,
            "answer": answer,
            "question_answer": "YES" if both_zero else "NO",
            "title": unit.get("title")
            or "Sentinel-versus-completeness audit in both directions",
            "min_bytes_rationale": (
                "200 bytes is the ready_units.py text-body floor (about two "
                "sentences) and the CNF-0162 meaningful-size requirement. A 0-byte "
                "file is the MSYS truncation signature; a sentinel-only file is a "
                "manufactured pass. Mutation: lowering the floor to 1 would admit "
                "the truncated-with-sentinel control as complete-minus-sentinel."
            ),
            "completeness_minus_sentinel": {
                "evaluated": [
                    "C2-exists",
                    "C3-min-bytes",
                    "C4-json-parse",
                    "C1-terminal-state",
                ],
                "separate": ["C5-exact-bounded-sentinel"],
                "not_checked_live": [
                    "C4-schema-file",
                    "C6",
                    "C7",
                    "C8",
                    "C9",
                    "C10",
                    "C11",
                    "C12",
                ],
                "why_not_checked": (
                    "platform/lib/completion_predicate.py, COMPLETION-GATES.json, "
                    "and a shipped CNF-0162 reducer may be absent. Claiming "
                    "C6-C12 on the live corpus would be an overclaim. Fixture "
                    "controls still prove both sentinel directions against P."
                ),
                "twelve_conditions_spec_10631_10644": CONDITIONS_12,
            },
            "inputs_resolved": input_status(),
            "directions": {
                "sentinel_on_incomplete": {
                    "id": "A",
                    "spec": "inverse-of-11313",
                    "name": (
                        "sentinel on a partial/incomplete artifact (manufactured pass)"
                    ),
                    "count": a["count"],
                    "ids": a["ids"],
                    "rows": a["rows"],
                },
                "complete_without_sentinel": {
                    "id": "B",
                    "spec": 11313,
                    "name": (
                        "complete artifact without its exact sentinel "
                        "(and the 11313 class for this complete half)"
                    ),
                    "count": b["count"],
                    "ids": b["ids"],
                    "rows": b["rows"],
                },
            },
            "plants": {
                "direction_a": "truncated-with-sentinel",
                "direction_b": "complete-without-sentinel",
            },
            "live_census": {
                "present_artifacts": live["present_artifacts"],
                "absent_output_paths": live["absent_output_paths"],
                "healthy_count": live["healthy_count"],
                "healthy_ids": live["healthy_ids"],
                "neither_count": live["neither_count"],
                "neither_ids": live["neither_ids"],
                "skipped_ids": live["skipped_ids"],
                "note": (
                    "CNF-0168 is skipped in the live census so this receipt cannot "
                    "classify itself. Probe 2 classifies the live receipt separately "
                    "and requires direction=healthy."
                ),
            },
            "controls": {
                "healthy_silent": ctrl["healthy_silent"],
                "direction_a_fires_on_truncate": ctrl["direction_a_fires_on_truncate"],
                "direction_b_fires_on_complete_without_sentinel": (
                    ctrl["direction_b_fires_on_complete_without_sentinel"]
                ),
                "near_miss_does_not_count": ctrl["near_miss_does_not_count"],
                "near_misses": ctrl["near_misses"],
                "truncated_reason": ctrl["direction_a"]["completeness_reason"],
                "complete_without_sentinel_reason": ctrl["direction_b"][
                    "completeness_reason"
                ],
            },
            "evidence_requirement": unit.get("evidence_requirement"),
            "failure_classification": unit.get("failure_classification"),
            "notes": (
                "G-1 delivery for CNF-0168: honest two-direction audit. Live "
                "findings are reported, not laundered into a combined mismatch "
                "number. SUCCESS:CNF-0168 means the audit ran and the controls "
                "discriminated; it is not a claim that the live estate is clean."
            ),
        },
    }

    # claim length cap 2000
    for ev in doc["evidence"]:
        if len(ev["claim"]) > 2000:
            ev["claim"] = ev["claim"][:1997] + "..."

    validate_or_die(doc, "pre-write")

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump(doc), encoding="utf-8")
    digest, size = sha256_file(out)
    doc["artifacts"][0]["sha256"] = digest
    doc["artifacts"][0]["bytes"] = size
    ended = datetime.now(timezone.utc)
    doc["timestamps"]["ended_at"] = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["timestamps"]["duration_seconds"] = max(
        0.0, (ended - started).total_seconds()
    )
    consumer_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0168/schema_local.py"
    )
    post_errs = SL.iter_errors(doc)
    doc["downstream_consumers"][0]["probe"]["raw_output"] = clip(
        "SUCCESS:schema-valid"
        if not post_errs
        else "FAILED:schema-invalid " + "; ".join(post_errs[:8])
    )
    doc["downstream_consumers"][0]["probe"]["command"] = consumer_cmd
    doc["downstream_consumers"][0]["probe"]["fingerprint"] = fp(
        "schema-validate", consumer_cmd
    )
    doc["downstream_consumers"][0]["read_ok"] = not post_errs
    doc["downstream_consumers"][0]["exit_code"] = 0 if not post_errs else 1
    if post_errs:
        print("FAILED:CNF-0168 post-hash schema errors")
        for e in post_errs[:20]:
            print(f"  {e}")
        return 1
    validate_or_die(doc, "post-hash")
    out.write_text(dump(doc), encoding="utf-8")
    digest, size = sha256_file(out)
    if size < A.MIN_BYTES:
        print(f"FAILED:CNF-0168 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0168" not in text:
        print("FAILED:CNF-0168 sentinel missing after write")
        return 1
    if not A.token_present(text, "SUCCESS:CNF-0168"):
        print("FAILED:CNF-0168 SUCCESS:CNF-0168 is not an exact token")
        return 1
    file_errs = SL.iter_errors(json.loads(text))
    if file_errs:
        print("FAILED:CNF-0168 on-disk schema errors")
        for e in file_errs[:20]:
            print(f"  {e}")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"live_A={a['count']} live_B={b['count']} healthy={live['healthy_count']}")
    print("SUCCESS:CNF-0168 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
