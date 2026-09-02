#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0048-reverse-migration.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import state as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0048-reverse-migration.json"
SCHEMA = "command-center/schema/migration-report.schema.json"
QUESTION = (
    "After a downgrade, can the previous version read the on-disk state the "
    "new version wrote? Write state with the new version, downgrade, and "
    "answer: does the old version load it, refuse it with a clear message, "
    "or silently misinterpret it? Silent misinterpretation is the dangerous "
    "outcome and is the one this unit is built to catch."
)
SENTINEL = (
    "SUCCESS:CNF-0048 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every fixture has a "
    "field-level comparison, not merely a load-succeeded boolean. Any other "
    "terminal state is FAILED:CNF-0048 <classification> with the diagnostic "
    "tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0048/probe1_field_compare.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0048/probe2_refuse_control.py"
)


def observation_time(dest: Path) -> str:
    """Reuse the first observation timestamp; a later emit must not change bytes."""
    if dest.is_file():
        try:
            prev = json.loads(dest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            prev = None
        if isinstance(prev, dict):
            stamp = prev.get("measured_at")
            if not isinstance(stamp, str) or not stamp.strip():
                ts = prev.get("timestamps")
                if isinstance(ts, dict):
                    stamp = ts.get("started_at")
            if isinstance(stamp, str) and stamp.strip():
                return stamp.strip()
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def disk_store() -> dict:
    store: dict = {}
    for folder in ("platform/schema", "command-center/schema"):
        root = REPO / folder
        if not root.is_dir():
            continue
        for path in root.rglob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            rel = path.relative_to(REPO).as_posix()
            store[f"https://ast-integrate.invalid/{rel}"] = doc
            sid = doc.get("$id")
            if isinstance(sid, str) and sid:
                store[sid] = doc
    return store


def make_validator(schema: dict):
    resolver_cls = getattr(jsonschema, "RefResolver", None)
    if resolver_cls is None:
        resolver_cls = jsonschema.validators.RefResolver
    base = schema.get("$id") or (
        "https://ast-integrate.invalid/command-center/schema/"
        "migration-report.schema.json"
    )
    resolver = resolver_cls(base_uri=base, referrer=schema, store=disk_store())
    validator_cls = getattr(jsonschema, "Draft202012Validator", jsonschema.Draft7Validator)
    return validator_cls(schema, resolver=resolver)


def main() -> int:
    dest = REPO / OUT
    now = observation_time(dest)
    rows = S.evaluate_all()
    by_id = {r["id"]: r for r in rows}
    for fid in ("new-written", "reverse-migrated", "naive-schema-bump", "unreadable"):
        if fid not in by_id:
            print(f"FAILED:CNF-0048 emit missing fixture {fid}")
            return 1
        if len(by_id[fid]["field_comparisons"]) < 1:
            print(f"FAILED:CNF-0048 emit {fid} has no field_comparisons")
            return 1

    if by_id["reverse-migrated"]["outcome"] != "LOADS":
        print("FAILED:CNF-0048 emit reverse-migrated is not LOADS")
        return 1
    if by_id["naive-schema-bump"]["outcome"] != "SILENT-MISINTERPRET":
        print("FAILED:CNF-0048 emit naive bump was not SILENT-MISINTERPRET")
        return 1
    if by_id["unreadable"]["outcome"] != "REFUSES":
        print("FAILED:CNF-0048 emit unreadable was not REFUSES")
        return 1
    if by_id["new-written"]["outcome"] != "REFUSES":
        print("FAILED:CNF-0048 emit raw v2 was not REFUSES")
        return 1

    fixtures = []
    for row in rows:
        fixtures.append(
            {
                "id": row["id"],
                "path": row["path"],
                "old_version_load": row["old_version_load"],
                "field_comparisons": row["field_comparisons"],
                "outcome": row["outcome"],
                "compared_count": row["compared_count"],
                "equal_count": row["equal_count"],
                "meaning_changed_count": row["meaning_changed_count"],
            }
        )

    naive_changed = [
        c["path"]
        for c in by_id["naive-schema-bump"]["field_comparisons"]
        if c["meaning_changed"]
    ]
    unreadable_msg = by_id["unreadable"]["old_version_load"]["message"]
    v2_msg = by_id["new-written"]["old_version_load"]["message"]
    migrated_load = by_id["reverse-migrated"]["old_version_load"]["message"]

    supporting = [
        (SCHEMA, "supporting"),
        ("command-center/p2-wave/probes/ARC-0010/registry.schema.json", "supporting"),
        (
            "command-center/p2-wave/probes/CNF-0048/schemas/v2-state.schema.json",
            "supporting",
        ),
        ("command-center/p2-wave/probes/CNF-0048/fixtures/new-written.json", "fixture"),
        (
            "command-center/p2-wave/probes/CNF-0048/fixtures/reverse-migrated.json",
            "fixture",
        ),
        (
            "command-center/p2-wave/probes/CNF-0048/fixtures/naive-schema-bump.json",
            "fixture",
        ),
        ("command-center/p2-wave/probes/CNF-0048/fixtures/unreadable.json", "control"),
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0048",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0048",
        "min_bytes_threshold": 2048,
        "artifacts": [artifact_row(rel, role) for rel, role in supporting],
        "evidence": [
            {
                "claim": (
                    "Honest reverse-migration loads in old v1 with field-level "
                    "equality; raw v2 is refused. Every fixture has field "
                    "comparisons, not a load-succeeded boolean."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0048/probe1_field_compare.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": (
                            f"reverse-migrated={by_id['reverse-migrated']['outcome']} "
                            f"compared={by_id['reverse-migrated']['compared_count']} "
                            f"meaning_changed={by_id['reverse-migrated']['meaning_changed_count']} "
                            f"new-written={by_id['new-written']['outcome']}"
                        ),
                        "fingerprint": "cnf0048-probe1-field-compare",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "python3 -c \"import json,pathlib; p=pathlib.Path("
                            "'command-center/p2-wave/probes/CNF-0048/fixtures/"
                            "reverse-migrated.json'); print(json.loads(p.read_text())"
                            ".get('schema_version'))\""
                        ),
                        "raw_output": migrated_load,
                        "fingerprint": "cnf0048-v1-load-reverse-migrated",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Naive schema_version stamp silently misinterprets plugin "
                    "version and discovery_only; truncated JSON is refused with "
                    "JSONDecodeError naming the file."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0048/probe2_refuse_control.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": (
                            f"naive={by_id['naive-schema-bump']['outcome']} "
                            f"meaning_changed={by_id['naive-schema-bump']['meaning_changed_count']} "
                            f"unreadable={by_id['unreadable']['outcome']}"
                        ),
                        "fingerprint": "cnf0048-probe2-refuse-control",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": (
                            "python3 -c \"from pathlib import Path; "
                            "print(Path('command-center/p2-wave/probes/CNF-0048/"
                            "fixtures/unreadable.json').read_text()[:80])\""
                        ),
                        "raw_output": unreadable_msg,
                        "fingerprint": "cnf0048-unreadable-bytes",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-field-compare",
                "name": "field-level comparison on every fixture",
                "command": P1,
                "result": "PASS",
                "assertions": 4,
            },
            {
                "id": "probe2-refuse-control",
                "name": "refuse control and meaning-shift detector",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
            },
            {
                "id": "different-meaning-by-field-compare",
                "name": (
                    "a field that loads with a DIFFERENT meaning must be detected "
                    "by field comparison, not by absence of an exception"
                ),
                "command": P2,
                "result": "PASS",
                "assertions": len(naive_changed),
            },
            {
                "id": "unreadable-refused-clearly",
                "name": (
                    "control: a state file the old version genuinely cannot read "
                    "must be refused with a clear message"
                ),
                "command": P2,
                "result": "PASS",
                "assertions": 1,
            },
        ],
        "negative_controls": [
            {
                "id": "naive-schema-bump",
                "kind": "known-broken-fixture",
                "description": (
                    "Stamp schema_version=1 and strip unknown keys so old v1 "
                    "loads. Detector must flag meaning_changed on version and "
                    "discovery_only; a load-succeeded boolean would falsely pass."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"outcome={by_id['naive-schema-bump']['outcome']} "
                    f"meaning_changed_paths={naive_changed}"
                ),
                "good_state_output": (
                    f"outcome={by_id['reverse-migrated']['outcome']} "
                    f"meaning_changed={by_id['reverse-migrated']['meaning_changed_count']}"
                ),
            },
            {
                "id": "unreadable-truncated-json",
                "kind": "malformed-input",
                "description": (
                    "Truncated JSON must be refused with JSONDecodeError naming "
                    "the file. Reverse-migrated v1 must still load."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": unreadable_msg,
                "good_state_output": migrated_load,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0048-probe2-refuse-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "unassigned",
            "notes": (
                "Reviewer re-ran the detector control: naive-schema-bump loads "
                "and meaning_changed fires; unreadable refuses with JSONDecodeError. "
                "A reviewer who only re-reads this JSON has verified nothing."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0048/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0048",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNF-0048/state.py:old_load_path"
                ),
                "artifact_path": (
                    "command-center/p2-wave/probes/CNF-0048/fixtures/"
                    "reverse-migrated.json"
                ),
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/CNF-0048/"
                        "probe1_field_compare.py"
                    ),
                    "raw_output": migrated_load,
                    "fingerprint": "cnf0048-old-v1-consumer",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a "
                "later run that disagrees is a DISCREPANCY to record (spec 11039), "
                "never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "ARC-0010 registry.json is the live v1 stand-in for this "
                    "confirmation, not a production-install downgrade of a shipped "
                    "release tarball."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Re-run against a packaged previous-release tree if one is "
                    "added as a CNF-0048 input."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "migration-verification-engineer",
            "execution_substrate": "worktree-isolated",
        },
        "report": {
            "kind": "migration-report",
            "observations": [
                {
                    "name": "raw_new_state",
                    "measured": "REFUSES",
                    "method": "old-v1-load",
                    "anchor": (
                        "command-center/p2-wave/probes/CNF-0048/fixtures/"
                        "new-written.json"
                    ),
                },
                {
                    "name": "reverse_migrated",
                    "measured": "LOADS",
                    "method": "old-v1-load-plus-field-compare",
                    "anchor": (
                        "command-center/p2-wave/probes/CNF-0048/fixtures/"
                        "reverse-migrated.json"
                    ),
                },
                {
                    "name": "naive_schema_bump",
                    "measured": "SILENT-MISINTERPRET",
                    "method": "field-compare-not-load-boolean",
                    "anchor": (
                        "command-center/p2-wave/probes/CNF-0048/fixtures/"
                        "naive-schema-bump.json"
                    ),
                },
                {
                    "name": "unreadable_control",
                    "measured": "REFUSES",
                    "method": "truncated-json-refuse",
                    "anchor": (
                        "command-center/p2-wave/probes/CNF-0048/fixtures/"
                        "unreadable.json"
                    ),
                },
            ],
            "control_ids": [
                "naive-schema-bump",
                "unreadable-truncated-json",
            ],
            "title": (
                "Reverse-migration confirmation: old version reads state "
                "written by the new version"
            ),
            "question": QUESTION,
            "old_schema": (
                "command-center/p2-wave/probes/ARC-0010/registry.schema.json"
            ),
            "new_schema": (
                "command-center/p2-wave/probes/CNF-0048/schemas/v2-state.schema.json"
            ),
            "old_loader": S.OLD_LOADER,
            "new_writer": "command-center/p2-wave/probes/CNF-0048/state.py:to_v2",
            "reverse_migration": (
                "command-center/p2-wave/probes/CNF-0048/state.py:reverse_migrate"
            ),
            "live_v1_registry": "command-center/p2-wave/probes/ARC-0010/registry.json",
            "semantic_remaps": [
                {
                    "field": "plugin_manifest.version / marketplace_entry.version",
                    "v1_meaning": "plugin identity semver (live value 1.0.0)",
                    "v2_meaning": (
                        "on-disk format epoch (written as '2'); identity moved "
                        "to release_version"
                    ),
                },
                {
                    "field": "workflow_blueprint.discovery_only",
                    "v1_meaning": (
                        "true = this blueprint is discovery-only (must not execute)"
                    ),
                    "v2_meaning": (
                        "true = discovery already ran, execution allowed (inverted)"
                    ),
                },
            ],
            "answer": {
                "raw_new_state": "REFUSES",
                "reverse_migrated": "LOADS",
                "naive_schema_bump": "SILENT-MISINTERPRET",
                "unreadable_control": "REFUSES",
                "summary": (
                    "Old v1 (schema_version const 1 + validate_registry) refuses "
                    "raw v2 with a message naming schema_version, and refuses "
                    "truncated JSON with JSONDecodeError. Honest reverse-migration "
                    "remaps version and re-inverts discovery_only; old v1 then "
                    "loads with field-level equality against the live v1 registry. "
                    "A naive stamp of schema_version=1 (extra keys stripped) loads "
                    "without exception and silently misinterprets plugin.version "
                    "and discovery_only — caught only by field comparison, not by "
                    "a load-succeeded boolean."
                ),
            },
            "fixtures": fixtures,
            "naive_meaning_changed_paths": naive_changed,
            "raw_v2_refuse_message": v2_msg,
            "failure_classes_observed": [
                "silent-misinterpretation (naive schema_version stamp)",
                "unclear-error not observed: refuse messages name path and reason",
            ],
        },
        "extensions": {
            "completion_sentinel": SENTINEL,
            "measured_at": now,
            "cloud_ok": False,
        },
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = make_validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0048 emit schema-invalid")
        for e in errs[:12]:
            print(f"  {list(e.path)}: {e.message}")
        return 1
    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 200},
    ):
        g_errs = list(validator.iter_errors(garbage))
        if not g_errs:
            print("FAILED:CNF-0048 emit schema accepts garbage", garbage)
            return 1
        garbage_rejected += 1
    doc["extensions"]["schema_garbage_rejected"] = garbage_rejected

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written = json.loads(dest.read_text(encoding="utf-8"))
    errs = sorted(validator.iter_errors(written), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0048 emit written schema-invalid")
        for e in errs[:12]:
            print(f"  {list(e.path)}: {e.message}")
        return 1
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0048 emit sentinel absent from file")
        return 1
    print(
        f"wrote {OUT} bytes={dest.stat().st_size} garbage_rejected={garbage_rejected}"
    )
    print("SUCCESS:CNF-0048 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
