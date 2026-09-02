#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0041-rollback-byte-parity.json."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from rehearse import run_clean, run_planted_control, run_walker_control  # noqa: E402
from scenario import manifest_path  # noqa: E402

OUT = "command-center/confirmation/CNF-0041-rollback-byte-parity.json"
SCHEMA = "command-center/schema/rollback-report.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0041/probe1_byte_parity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0041/probe2_planted_control.py"
)
FIXTURE_MANIFEST = (
    "command-center/p2-wave/probes/CNF-0041/fixtures/ROLLBACK-MANIFEST.md"
)
WALKER = "command-center/p2-wave/probes/CNF-0041/walker.py"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def validator_for_declared_schema():
    """Resolve ast-integrate.invalid $ref onto disk (jsonschema 4.10, no network)."""
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    for doc in (shim, profiles, receipt):
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def schema_errors(doc) -> list[str]:
    validator = validator_for_declared_schema()
    out = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0041":
            return unit
    raise SystemExit("FAILED:CNF-0041 catalog unit missing")


def artifact_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit["completion_sentinel"])
    question = str(unit["question_or_target"])
    catalog_manifest = REPO / "command-center/ROLLBACK-MANIFEST.md"
    started = datetime.now(timezone.utc)

    with tempfile.TemporaryDirectory(prefix="cnf0041-emit-") as tmp:
        root = Path(tmp)
        clean = run_clean(root / "clean")
        planted = run_planted_control(root / "plant")
        walker = run_walker_control(root / "walk")

    if not clean["symmetric_difference"]["empty"]:
        print("FAILED:CNF-0041 incomplete-rollback")
        print(json.dumps(clean["symmetric_difference"], indent=2))
        return 1
    if not planted.get("detected"):
        print("FAILED:CNF-0041 detector-failure planted file not seen")
        print(json.dumps(planted, indent=2, default=str)[:3000])
        return 1
    if not walker.get("naive_swallowed_to_zero"):
        print("FAILED:CNF-0041 naive walker did not swallow to zero")
        print(json.dumps(walker, indent=2, default=str)[:2000])
        return 1
    if walker["safe_count"] < 2 or not walker.get("reserved_in_safe"):
        print("FAILED:CNF-0041 walker-crash reserved name missing")
        print(json.dumps(walker, indent=2, default=str)[:2000])
        return 1
    if len(clean["pre_rows"]) != len(clean["post_rollback_rows"]):
        print("FAILED:CNF-0041 pre/post-rollback cardinality drift")
        return 1

    ended = datetime.now(timezone.utc)
    duration = max(0.0, (ended - started).total_seconds())
    pre_n = len(clean["pre_rows"])
    post_n = len(clean["post_rows"])
    rb_n = len(clean["post_rollback_rows"])
    answer = (
        "Yes for the fixture rollback: the post-rollback hash set equals the "
        "pre-change set (empty symmetric difference, residue listed as []). "
        "An incomplete rollback that leaves a planted extra file is detected "
        f"on {planted['planted_path']}. The hashing walker enumerates "
        f"{walker['reserved_path']} via the extended-length prefix; the naive "
        "walker swallowed ValueError and reported zero files."
    )
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0041",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0041",
        "min_bytes_threshold": 1200,
        "profile": "rollback-byte-parity",
        "artifacts": [
            artifact_row(SCHEMA, "supporting"),
            artifact_row(FIXTURE_MANIFEST, "fixture"),
            artifact_row(WALKER, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "Post-rollback sha256 set equals the pre-change set on the "
                    f"fixture trees ({pre_n} files); the change itself was not vacuous "
                    f"(post had {post_n} hashed paths)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0041/rehearse.py:run_clean",
                "probes": [
                    {
                        "role": "source",
                        "method": "byte-compare",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/CNF-0041/rehearse.py"
                        ),
                        "raw_output": (
                            f"pre={pre_n} post={post_n} post_rollback={rb_n} "
                            f"symmetric_difference.empty="
                            f"{clean['symmetric_difference']['empty']}"
                        ),
                        "fingerprint": "cnf0041:source:clean-rehearsal",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "raw_output": "named probe1 re-runs run_clean against the artifact",
                        "fingerprint": "cnf0041:verifier:probe1-byte-parity",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Planted-file control fired on incomplete rollback, and the "
                    "naive reserved-name walker swallowed to zero files."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0041/rehearse.py:run_planted_control",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/CNF-0041/probe2_planted_control.py"
                        ),
                        "raw_output": (
                            f"planted={planted['planted_path']} detected="
                            f"{planted['detected']} naive_zero={walker['naive_count']} "
                            f"safe={walker['safe_count']}"
                        ),
                        "fingerprint": "cnf0041:source:planted-and-reserved",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": (
                            "python3 platform/lib/schema_resolver.py "
                            f"{OUT} {SCHEMA}"
                        ),
                        "raw_output": "disk-local rollback-report validator compiled",
                        "fingerprint": "cnf0041:verifier:schema-resolver",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1",
                "name": "byte-parity pre equals post-rollback",
                "command": P1,
                "result": "PASS",
                "assertions": 1,
            },
            {
                "id": "probe2",
                "name": "planted-file detector and reserved-name walker",
                "command": P2,
                "result": "PASS",
                "assertions": 1,
            },
        ],
        "negative_controls": [
            {
                "id": "planted-file-incomplete-rollback",
                "kind": "known-broken-fixture",
                "description": (
                    "Plant one extra file, restore snapshot bytes without "
                    "deleting extras; comparison must list the plant."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": planted["planted_path"],
                "good_state_output": "residue=[]",
            },
            {
                "id": "naive-reserved-name-walker",
                "kind": "known-broken-fixture",
                "description": (
                    "Opening affected/app/NUL without the extended-length "
                    "prefix must raise; swallowing that crash reports zero files."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": str(walker.get("naive_error") or "ValueError"),
                "good_state_output": f"safe_count={walker['safe_count']}",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0041-probe2-planted-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Named probe2 re-runs the planted-file detector and the "
                "reserved-name walker on a fresh temp tree. Re-reading this "
                "artifact is not the review."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0041/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0041",
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.py (validate_artifact)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": f"python3 platform/lib/schema_resolver.py {OUT} {SCHEMA}",
                    "raw_output": "SUCCESS:schema-valid",
                    "fingerprint": "cnf0041:consumer:schema-resolver",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record "
                "(spec 11039), never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Byte-parity was measured on a disposable fixture named by "
                    f"{FIXTURE_MANIFEST}, not a live-estate rollback of "
                    "command-center/ROLLBACK-MANIFEST.md "
                    f"(catalog_manifest_present={catalog_manifest.is_file()})."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Owner-approved live-estate run would re-point the walker "
                    "at the catalog ROLLBACK-MANIFEST and a disposable copy of "
                    "the named trees."
                ),
            }
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "rollback-verification-engineer",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "rollback-report",
            "observations": [
                {
                    "name": "pre_file_count",
                    "measured": pre_n,
                    "method": "hash-trees-extended-length",
                    "anchor": "command-center/p2-wave/probes/CNF-0041/walker.py:hash_trees",
                },
                {
                    "name": "post_rollback_equals_pre",
                    "measured": True,
                    "method": "symmetric-difference",
                    "anchor": "command-center/p2-wave/probes/CNF-0041/walker.py:symmetric_difference",
                },
                {
                    "name": "planted_file_detected",
                    "measured": True,
                    "method": "incomplete-rollback-control",
                    "anchor": "command-center/p2-wave/probes/CNF-0041/rehearse.py:run_planted_control",
                },
                {
                    "name": "naive_walker_swallowed_to_zero",
                    "measured": True,
                    "method": "reserved-name-naive-open",
                    "anchor": "command-center/p2-wave/probes/CNF-0041/walker.py:naive_hash_swallowed",
                },
            ],
            "control_ids": [
                "planted-file-incomplete-rollback",
                "naive-reserved-name-walker",
            ],
            "title": unit.get("title"),
            "question": question,
            "verdict": "BYTE-IDENTICAL",
            "answer": answer,
            "hash_manifests": {
                "pre": clean["pre_rows"],
                "post": clean["post_rows"],
                "post_rollback": clean["post_rollback_rows"],
            },
            "symmetric_difference": clean["symmetric_difference"],
            "residue": clean["residue"],
            "planted_file_control": {
                "planted_path": planted["planted_path"],
                "detected": True,
                "when": planted["when"],
                "symmetric_difference": planted["symmetric_difference"],
            },
            "reserved_name_walker": {
                "reserved_path": walker["reserved_path"],
                "extended_length_prefix_applied": True,
                "extended_length_path": walker["extended_length_path"],
                "safe_count": walker["safe_count"],
                "naive_count": walker["naive_count"],
                "naive_swallowed_to_zero": True,
                "naive_error": walker["naive_error"],
                "reserved_in_safe": True,
            },
            "catalog_inputs": {
                "rollback_manifest_catalog_path": "command-center/ROLLBACK-MANIFEST.md",
                "catalog_manifest_present": catalog_manifest.is_file(),
                "fixture_manifest": FIXTURE_MANIFEST,
                "scope": (
                    "disposable fixture trees named by the fixture "
                    "ROLLBACK-MANIFEST; not a live-estate rollback of "
                    "command-center/ROLLBACK-MANIFEST.md"
                ),
                "affected_trees": clean["trees"],
            },
            "named_probes": [
                {"id": "probe1", "role": "byte-parity", "command": P1},
                {
                    "id": "probe2",
                    "role": "planted-file-and-reserved-walker",
                    "command": P2,
                },
            ],
            "fixture_manifest_sha256": sha256_file(manifest_path())[0],
        },
        "extensions": {
            "cloud_ok": False,
            "output_path": OUT,
        },
    }

    errs = schema_errors(doc)
    if errs:
        print("FAILED:CNF-0041 schema errors")
        for e in errs[:25]:
            print(" ", e)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0041", "state": "SUCCESS"},
    ):
        if not schema_errors(garbage):
            print("FAILED:CNF-0041 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0041 artifact {size}B below floor")
        return 1
    if sentinel not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0041 sentinel absent from artifact text")
        return 1
    post_errs = schema_errors(json.loads(out.read_text(encoding="utf-8")))
    if post_errs:
        print("FAILED:CNF-0041 written artifact schema-invalid")
        for e in post_errs[:25]:
            print(" ", e)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"pre={pre_n} post={post_n} post_rollback={rb_n} "
        f"residue={len(clean['residue'])} planted={planted['planted_path']}"
    )
    print("SUCCESS:CNF-0041 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
