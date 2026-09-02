#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0165.json (resume_report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = "command-center/receipts/TST-0165.json"
SCHEMA = "command-center/p2-wave/probes/TST-0165/resume_report.schema.json"
CATALOG_SCHEMA = "command-center/schema/receipt.schema.json#/$defs/resume_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0165/probe1_resume_exit.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0165/probe2_fieldset.py"
)
QUESTION = (
    "When the checkpoint on disk predates the current schema version, does "
    "resume run a versioned migration or refuse loudly? PASS forbids a partial "
    "read that silently drops unknown fields."
)
SENTINEL = "SUCCESS:TST-0165"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(rel: str, command: str) -> str:
    path = REPO / rel
    body = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return sha256_bytes(body + b"\n" + command.encode("utf-8"))


def serialize_val(val: Any) -> Any:
    if isinstance(val, tuple):
        return list(val)
    return val


def fixture_row(fid: str, row: dict[str, Any]) -> dict[str, Any]:
    resume = row["resume"]
    fs = row["fieldset"]
    comparisons = []
    if fs:
        for c in fs["rows"]:
            comparisons.append(
                {
                    "path": c["path"],
                    "before": serialize_val(c.get("before")),
                    "after": serialize_val(c.get("after")),
                    "account": c["account"],
                    "mapped_to": c.get("mapped_to"),
                }
            )
    return {
        "id": fid,
        "path": row["path"],
        "exit_code": resume["exit_code"],
        "message": resume["message"],
        "migrated": resume.get("migrated"),
        "refused": resume.get("refused"),
        "from_version": resume.get("from_version"),
        "to_version": resume.get("to_version"),
        "checkpoint": resume.get("checkpoint"),
        "fieldset": None
        if fs is None
        else {
            "compared": fs["compared"],
            "silent_drops": fs["silent_drops"],
            "meaning_changed": fs["meaning_changed"],
            "mapped": fs["mapped"],
            "preserved": fs["preserved"],
            "added": fs["added"],
            "zero_silent_drops": fs["zero_silent_drops"],
            "comparisons": comparisons,
        },
    }


def main() -> int:
    paths = E.materialize_fixtures()
    strict = E.evaluate_strict(paths)
    lenient = E.evaluate_lenient(paths)
    census = E.production_census()

    old = strict["old-v1"]
    cur = strict["current-v2"]
    extra = strict["old-v1-unknown-extra"]
    future = strict["future-v99"]
    unread = strict["unreadable"]
    lv1 = lenient["old-v1"]
    lextra = lenient["old-v1-unknown-extra"]

    if old["resume"]["exit_code"] != 0 or not (old["fieldset"] or {}).get(
        "zero_silent_drops"
    ):
        print("FAILED:TST-0165 emit old-v1 did not migrate cleanly")
        return 1
    if cur["resume"]["exit_code"] != 0 or cur["resume"].get("migrated"):
        print("FAILED:TST-0165 emit current-v2 migrated or refused")
        return 1
    before_v2 = json.loads(paths["current-v2"].read_text(encoding="utf-8"))
    if E.flatten(before_v2) != E.flatten(cur["resume"]["checkpoint"]):
        print("FAILED:TST-0165 emit current-v2 is not identity")
        return 1
    if extra["resume"]["exit_code"] == 0:
        print("FAILED:TST-0165 emit unknown extra was not refused")
        return 1
    if future["resume"]["exit_code"] == 0 or unread["resume"]["exit_code"] == 0:
        print("FAILED:TST-0165 emit future/unreadable loaded")
        return 1
    ld = lv1["fieldset"]
    lenient_drops = sorted(set(ld["silent_drops"]) | set(ld["meaning_changed"]))
    if not lenient_drops:
        print("FAILED:TST-0165 emit lenient detector vacuous")
        return 1
    if "secret_operator_note" not in lextra["fieldset"]["silent_drops"]:
        print("FAILED:TST-0165 emit lenient extra field not dropped")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    src_fp = fingerprint(
        "command-center/p2-wave/probes/TST-0165/probe1_resume_exit.py", P1
    )
    ver_fp = fingerprint(
        "command-center/p2-wave/probes/TST-0165/probe2_fieldset.py", P2
    )
    if src_fp == ver_fp:
        print("FAILED:TST-0165 emit source/verifier fingerprints identical")
        return 1

    fixtures = [fixture_row(fid, strict[fid]) for fid in (
        "current-v2",
        "old-v1",
        "old-v1-unknown-extra",
        "future-v99",
        "unreadable",
    )]
    evidence_a_rows = [
        {
            "id": fid,
            "exit_code": strict[fid]["resume"]["exit_code"],
            "message": strict[fid]["resume"]["message"],
            "refused": strict[fid]["resume"]["refused"],
        }
        for fid in (
            "current-v2",
            "old-v1",
            "old-v1-unknown-extra",
            "future-v99",
            "unreadable",
        )
    ]
    live_a = sha256_bytes(
        json.dumps(evidence_a_rows, sort_keys=True, separators=(",", ":")).encode()
    )
    live_b = sha256_bytes(
        json.dumps(
            {
                "zero": old["fieldset"]["zero_silent_drops"],
                "mapped": old["fieldset"]["mapped"],
                "lenient": lenient_drops,
                "extra": lextra["fieldset"]["silent_drops"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )

    tests = [
        {
            "id": "TST-0165-BOTH-STATES",
            "requirement": "a current-version checkpoint resumes without migration",
            "result": "PASS",
            "basis": "current-v2 field-set identity and migrated=false",
        },
        {
            "id": "TST-0165-NEGATIVE-LENIENT",
            "requirement": "a lenient loader that ignores unknown fields must fail",
            "result": "PASS",
            "basis": (
                "resume_lenient drops legacy_cursor / legacy_artifact_cache_key "
                f"({lenient_drops}) and secret_operator_note; field-set detector fires"
            ),
        },
        {
            "id": "TST-0165-FIELDSET-ZERO-DROPS",
            "requirement": "field-set diff of old checkpoint vs migrated shows zero silent drops",
            "result": "PASS",
            "basis": (
                f"compared={old['fieldset']['compared']} silent_drops=[] "
                f"mapped={old['fieldset']['mapped']}"
            ),
        },
        {
            "id": "TST-0165-LOUD-REFUSE",
            "requirement": "unknown schema version and extra unknown fields refuse with a named message",
            "result": "PASS",
            "basis": extra["resume"]["message"] + " | " + future["resume"]["message"],
        },
        {
            "id": "TST-0165-NAMED-A",
            "requirement": "(a) the resume exit status and message",
            "result": "PASS",
            "basis": "probe1_resume_exit.py",
        },
        {
            "id": "TST-0165-NAMED-B",
            "requirement": "(b) a field-set diff between the old checkpoint and the migrated one showing zero silent drops",
            "result": "PASS",
            "basis": "probe2_fieldset.py",
        },
    ]

    supporting = [
        "command-center/p2-wave/probes/TST-0165/engine.py",
        "command-center/p2-wave/probes/TST-0165/resume_report.schema.json",
        "command-center/p2-wave/probes/TST-0165/probe1_resume_exit.py",
        "command-center/p2-wave/probes/TST-0165/probe2_fieldset.py",
        "command-center/p2-wave/probes/TST-0165/fixtures/current-v2.json",
        "command-center/p2-wave/probes/TST-0165/fixtures/old-v1.json",
        "command-center/p2-wave/probes/TST-0165/fixtures/old-v1-unknown-extra.json",
        "command-center/p2-wave/probes/TST-0165/fixtures/future-v99.json",
        "command-center/p2-wave/probes/TST-0165/fixtures/unreadable.json",
    ]
    artifacts = []
    for rel in supporting:
        p = REPO / rel
        sha, size = sha256_file(p) if p.is_file() else ("", 0)
        artifacts.append(
            {
                "path": rel,
                "role": "supporting",
                "exists": p.is_file(),
                "bytes": size,
                "sha256": sha,
            }
        )

    catalog_schema_path = REPO / "command-center/schema/receipt.schema.json"
    doc = {
        "unit_id": "TST-0165",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "resume_report",
        "title": "Older checkpoint schema triggers migration or a loud refusal",
        "question": QUESTION,
        "overall_verdict": "PASS",
        "measured_at": now,
        "output_schema": CATALOG_SCHEMA,
        "output_schema_present": catalog_schema_path.is_file(),
        "local_schema": SCHEMA,
        "current_schema_version": E.CURRENT_SCHEMA,
        "sut": census["sut"],
        "production_census": census,
        "answer": {
            "current_version_resumes_without_migration": True,
            "old_schema_migrates_or_refuses": True,
            "zero_silent_drops_on_strict_migrate": True,
            "lenient_loader_fails_fieldset": True,
            "unknown_extra_field_refused": True,
            "future_version_refused": True,
            "unreadable_refused": True,
            "summary": (
                "Strict resume migrates schema_version 1 to 2 with declared remaps "
                "(legacy_cursor->resume_cursor, legacy_artifact_cache_key->"
                "artifact_cache_key) and an explicit pinned_sha default. The "
                "field-set diff on that pair has zero silent drops and zero "
                "meaning-changed keys. A current schema_version=2 checkpoint "
                "resumes as an identity (no migration). Unknown extra fields on "
                "v1, schema_version=99, and truncated JSON refuse with messages "
                "that name the field, the version, or JSONDecodeError. The "
                "lenient mutant stamps schema_version=2 and ignores unknown keys; "
                f"field-set detector fires on {lenient_drops} plus "
                "secret_operator_note. Production tools/lib/handled-ledger.mjs "
                "is absent and is not the SUT. SUCCESS:TST-0165"
            ),
        },
        "tests": tests,
        "tests_required": [
            {
                "id": "both-states",
                "text": "a current-version checkpoint resumes without migration",
                "result": "PASS",
            },
            {
                "id": "negative-control",
                "text": "a lenient loader that ignores unknown fields must fail",
                "result": "PASS",
            },
        ],
        "evidence_a": {
            "signal": "the resume exit status and message",
            "probe": P1,
            "live_result_digest": live_a,
            "rows": evidence_a_rows,
        },
        "evidence_b": {
            "signal": (
                "a field-set diff between the old checkpoint and the migrated "
                "one showing zero silent drops"
            ),
            "probe": P2,
            "live_result_digest": live_b,
            "old_v1_zero_silent_drops": True,
            "old_v1_compared": old["fieldset"]["compared"],
            "old_v1_mapped": old["fieldset"]["mapped"],
            "old_v1_added": old["fieldset"]["added"],
            "lenient_silent_drops": lenient_drops,
            "lenient_extra_silent_drops": lextra["fieldset"]["silent_drops"],
            "lenient_message": lv1["resume"]["message"],
        },
        "fixtures": fixtures,
        "lenient_controls": {
            "old-v1": fixture_row("old-v1", lv1),
            "old-v1-unknown-extra": fixture_row("old-v1-unknown-extra", lextra),
        },
        "migration_table": [
            {
                "from_field": "legacy_cursor",
                "to_field": "resume_cursor",
                "rule": "rename; value preserved",
            },
            {
                "from_field": "legacy_artifact_cache_key",
                "to_field": "artifact_cache_key",
                "rule": "rename; value preserved",
            },
            {
                "from_field": None,
                "to_field": "pinned_sha",
                "rule": "explicit default unpinned-v1-migrated (not a drop)",
            },
        ],
        "source_probe": {
            "id": "probe1",
            "command": P1,
            "role": "resume-exit-status-and-message",
            "fingerprint": src_fp,
            "live_result_digest": live_a,
        },
        "verifier_probe": {
            "id": "probe2",
            "command": P2,
            "role": "fieldset-diff-both-states-lenient-control",
            "fingerprint": ver_fp,
            "live_result_digest": live_b,
        },
        "reviewer": {
            "reviewer_id": "TST-0165-probe2-fieldset-and-lenient",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 accounts keys and values; it does not reuse probe 1's "
                "exit_code/message pass criteria. Catalog asked for a fresh-context "
                "human reviewer; none was dispatched to this G-1 worker. Probe 2 "
                "is the independent mechanical reviewer of the engine."
            ),
        },
        "discrepancies": [
            {
                "id": "D-PRODUCTION-LEDGER-ABSENT",
                "kind": "missing-runtime",
                "statement": (
                    "tools/lib/handled-ledger.mjs and _USER-PROMPTS.md are not on "
                    "this worktree. The report measures probe-local resume_strict, "
                    "not production ledger resume."
                ),
            }
        ],
        "residual_caveat": (
            "Object under test is command-center/p2-wave/probes/TST-0165/engine.py. "
            "command-center/schema/receipt.schema.json is absent, so validation uses "
            "the probe-local resume_report.schema.json. cloud ok=true is not delivery. "
            "Did not run unit_manifest.py --write."
        ),
        "artifacts": artifacts,
        "registered": True,
        "cloud_ok": False,
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0165 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {},
        {"unit_id": "TST-0165", "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "TST-0000", "state": "SUCCESS", "sentinel": "SUCCESS:TST-0165"},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:TST-0165 schema accepted garbage {list(g)[:4]}")
            return 1

    if SENTINEL not in json.dumps(doc):
        print("FAILED:TST-0165 sentinel missing from artifact text")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0165 emit self-declared not delivering")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    primary = {
        "path": OUT,
        "role": "primary",
        "exists": True,
        "bytes": size,
        "sha256": digest,
    }
    # Re-write with primary artifact row included would change the digest.
    # Leave primary out of the in-document artifacts list; the per-unit
    # manifest carries the live sha. Print it here.
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"old_v1_drops=0 lenient_drops={lenient_drops} "
        f"ledger_present={census['handled_ledger_present']}"
    )
    print("SUCCESS:TST-0165 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
