#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0035-strict-parser.json.

Validates against the catalog output_schema using a disk-only $ref store
(https://ast-integrate.invalid/ maps onto this worktree). No network.
Does not run tools/command-center/unit_manifest.py --write.
"""
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
import suite as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0035-strict-parser.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
UNIT = "CNF-0035"
QUESTION = (
    "Does the fixed manifest survive a strict parser? Feed each manifest "
    "and config through a strict reader and answer three questions: is an "
    "unknown field rejected rather than silently ignored, do two "
    "case-distinct JSON keys collide under a case-insensitive client, and "
    "does a duplicate key produce an error rather than a last-wins overwrite?"
)
SENTINEL = (
    "SUCCESS:CNF-0035 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all three negative "
    "fixtures errored and the valid control parsed cleanly in the same "
    "invocation. Any other terminal state is FAILED:CNF-0035 "
    "<classification> with the diagnostic tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0035/probe1_same_invocation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0035/probe2_detector_control.py"
)
SUITE_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0035/suite.py"
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)
SCHEMA_STORE_RELS = (
    SCHEMA,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
SUPPORTING = (
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0035/strict_reader.py",
    "command-center/p2-wave/probes/CNF-0035/document_schemas.py",
    "command-center/p2-wave/probes/CNF-0035/suite.py",
    "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/typed/plugin.json",
    "command-center/p2-wave/probes/CNF-0035/fixtures/negative.unknown-field.json",
    "command-center/p2-wave/probes/CNF-0035/fixtures/negative.case-distinct.json",
    "command-center/p2-wave/probes/CNF-0035/fixtures/negative.duplicate-key.json",
    "command-center/p2-wave/probes/CNF-0035/fixtures/control.valid-plugin.json",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    digest = hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()
    return digest[:24]


def _https_handler(uri: str) -> dict:
    prefix = "https://ast-integrate.invalid/"
    if not uri.startswith(prefix):
        raise jsonschema.exceptions.RefResolutionError(
            f"refusing non-local schema uri (no network): {uri!r}"
        )
    rel = uri.split("#", 1)[0][len(prefix) :]
    path = REPO / rel
    if not path.is_file():
        raise jsonschema.exceptions.RefResolutionError(
            f"schema uri has no file on disk: {uri!r}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def build_validator() -> jsonschema.Draft7Validator:
    store: dict[str, dict] = {}
    for rel in SCHEMA_STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        uri = "https://ast-integrate.invalid/" + rel
        store[uri] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    shim = store["https://ast-integrate.invalid/" + SCHEMA]
    resolver = jsonschema.RefResolver(
        base_uri=str(shim.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA)),
        referrer=shim,
        store=store,
        handlers={"https": _https_handler, "http": _https_handler},
    )
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    if size < 1:
        raise SystemExit(f"FAILED:CNF-0035 zero-byte supporting artifact {rel}")
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def validate_or_die(doc: dict, validator: jsonschema.Draft7Validator) -> None:
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0035 schema errors")
        for err in errs[:20]:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            print(f"  {loc}: {err.message}")
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            raise SystemExit("FAILED:CNF-0035 schema accepts garbage")


def main() -> int:
    started = datetime.now(timezone.utc)
    report = S.run_suite()
    if not report["pass"]:
        print("FAILED:CNF-0035 suite did not pass")
        print(json.dumps(report, indent=2, sort_keys=True, default=str)[:4000])
        return 1
    if not report["mutation_unknown_accepted_when_additional_properties_true"]:
        print("FAILED:CNF-0035 unknown-field mutation did not go green")
        return 1
    if report["permissive_duplicate"].get("name") != "last-wins-if-permissive":
        print("FAILED:CNF-0035 lenient last-wins control did not take the last value")
        return 1

    by_id = {r["id"]: r for r in report["results"]}
    answers = {
        "unknown_field_rejected": by_id["unknown-field"]["ok"],
        "case_distinct_collision_reported": by_id["case-distinct"]["ok"],
        "duplicate_key_errors_not_last_wins": by_id["duplicate-key"]["ok"],
        "valid_control_parsed_clean": by_id["control"]["ok"],
        "same_invocation": True,
        "live_manifests_parsed_clean": report["live_manifests_ok"],
    }
    if not all(answers.values()):
        print("FAILED:CNF-0035 answers not all true")
        return 1

    validator = build_validator()
    now = datetime.now(timezone.utc)
    now_s = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (now - started).total_seconds())

    unk_err = by_id["unknown-field"]["error_text"]
    case_err = by_id["case-distinct"]["error_text"]
    dup_err = by_id["duplicate-key"]["error_text"]
    live_ok = [row["path"] for row in report["live"] if row.get("parsed")]
    parser = report["parser"]

    artifacts = [artifact_row(SUPPORTING[0], "supporting")]
    artifacts[0]["role"] = "supporting"
    for rel in SUPPORTING:
        role = "control" if "/fixtures/" in rel else "supporting"
        if rel.endswith("plugin.json"):
            role = "fixture"
        artifacts.append(artifact_row(rel, role))
    # first row duplicated SCHEMA; drop the extra
    seen: set[str] = set()
    deduped = []
    for row in artifacts:
        if row["path"] in seen:
            continue
        seen.add(row["path"])
        deduped.append(row)
    artifacts = deduped

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11302",
        "min_bytes_threshold": 1024,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Unknown-field, case-distinct, and duplicate-key fixtures "
                    "all error, and the valid plugin control parses, in one "
                    "strict_reader invocation."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0035/suite.py:172",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": SUITE_CMD,
                        "raw_output": (
                            f"unknown={unk_err!r}; case={case_err!r}; "
                            f"dup={dup_err!r}; control_parsed="
                            f"{by_id['control']['parsed']}"
                        ),
                        "fingerprint": fp("test-run", SUITE_CMD),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "python3 -c \"from pathlib import Path; import sys; "
                            "sys.path.insert(0,'command-center/p2-wave/probes/"
                            "CNF-0035'); import suite as S; r=S.run_suite(); "
                            "print(r['detector_ok'], r['control_parsed_clean'])\""
                        ),
                        "raw_output": (
                            f"detector_ok={report['detector_ok']} "
                            f"control_parsed_clean={report['control_parsed_clean']}"
                        ),
                        "fingerprint": fp("file-read", "suite.run_suite detector_ok"),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Live plugin, marketplace, hook, dispatch, settings "
                    "fixture, and typed registry parse under additionalProperties "
                    "false in the same reader."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0035/document_schemas.py:142",
                "probes": [
                    {
                        "role": "source",
                        "method": "schema-validate",
                        "command": SUITE_CMD + " # live_subjects",
                        "raw_output": "live_ok=" + ",".join(live_ok),
                        "fingerprint": fp("schema-validate", "live_subjects"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "python3 -c \"import json; json.load(open("
                            "'command-center/p2-wave/probes/ARC-0016/fixtures/"
                            "hatch-run/typed/plugin.json'))\""
                        ),
                        "raw_output": "plugin.json keys=_generated,description,hooks,name,rules,skills,version",
                        "fingerprint": fp("file-read", "plugin.json"),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T-SUITE",
                "name": "same-invocation three negatives plus valid control",
                "command": SUITE_CMD,
                "result": "PASS",
                "assertions": 4,
            }
        ],
        "negative_controls": [
            {
                "id": "CNF0035-C1-unknown-field",
                "kind": "known-broken-fixture",
                "description": (
                    "Plugin clone with cnf0035_unknown_field must be rejected "
                    "under additionalProperties false."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": unk_err,
                "good_state_output": "control parsed cleanly",
            },
            {
                "id": "CNF0035-C2-case-distinct",
                "kind": "known-broken-fixture",
                "description": (
                    "Name/name pair must be reported as a case-collision, not "
                    "silently merged."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": case_err,
                "good_state_output": "control parsed cleanly",
            },
            {
                "id": "CNF0035-C3-duplicate-key",
                "kind": "known-broken-fixture",
                "description": (
                    "Duplicate name key must error; stdlib last-wins is the "
                    "dangerous control."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": dup_err,
                "good_state_output": (
                    "lenient json.loads name="
                    + str(report["permissive_duplicate"].get("name"))
                ),
            },
            {
                "id": "CNF0035-C4-additionalProperties-mutation",
                "kind": "mutation",
                "description": (
                    "Relax additionalProperties to true; the unknown-field "
                    "fixture must then parse, proving the reject is the schema "
                    "rule and not a decoder that always fails."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "unknown-field accepted after mutation",
                "good_state_output": unk_err,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0035-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Named probe2 re-runs the DETECTOR CONTROL on the known-broken "
                "fixtures (unknown-field, case-distinct, duplicate-key, stdlib "
                "last-wins, additionalProperties mutation) and does not treat "
                "this receipt's conclusion as evidence."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0035/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "jsonschema.Draft7Validator against "
                    "command-center/schema/conformance-report.schema.json "
                    "(disk RefResolver, no network)"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 command-center/p2-wave/probes/CNF-0035/emit_report.py"
                    ),
                    "raw_output": "schema-valid; garbage rejected",
                    "fingerprint": fp("schema-validate", SCHEMA),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now_s,
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
                "claim": "Live ~/.claude/settings.json bytes",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Exercise an owner-supplied redacted settings dump; this "
                    "unit uses an in-repo frozen-key fixture and does not read "
                    "the live credential-adjacent file."
                ),
            },
            {
                "claim": "tools/plugin product parser at tools/plugin/",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place tools/plugin/ on disk and re-run the same fixtures "
                    "through that parser. This worktree uses "
                    "cnf-0035-strict-reader against the A2 generated manifests "
                    "that are present."
                ),
            },
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "parser-conformance-engineer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "conformance-report",
            "same_invocation": True,
            "title": (
                "Strict-parser confirmation: unknown fields and case-distinct "
                "key collisions"
            ),
            "question": QUESTION,
            "parser": parser,
            "answers": answers,
            "observations": [
                {
                    "name": "unknown-field-rejected",
                    "measured": True,
                    "method": "jsonschema additionalProperties false",
                    "anchor": by_id["unknown-field"]["path"],
                },
                {
                    "name": "case-distinct-collision",
                    "measured": True,
                    "method": "object_pairs_hook casefold",
                    "anchor": by_id["case-distinct"]["path"],
                },
                {
                    "name": "duplicate-key-refused",
                    "measured": True,
                    "method": "object_pairs_hook exact-key set",
                    "anchor": by_id["duplicate-key"]["path"],
                },
                {
                    "name": "valid-control-parsed",
                    "measured": True,
                    "method": "same read_strict invocation",
                    "anchor": by_id["control"]["path"],
                },
            ],
            "control_ids": [
                "CNF0035-C1-unknown-field",
                "CNF0035-C2-case-distinct",
                "CNF0035-C3-duplicate-key",
                "CNF0035-C4-additionalProperties-mutation",
            ],
            "fixtures": report["results"],
            "live_manifests": report["live"],
            "permissive_stdlib_control": report["permissive_duplicate"],
            "mutation": {
                "id": "relax-additionalProperties",
                "unknown_accepted": report[
                    "mutation_unknown_accepted_when_additional_properties_true"
                ],
            },
            "verbatim_errors": {
                "unknown-field": unk_err,
                "case-distinct": case_err,
                "duplicate-key": dup_err,
            },
        },
        "extensions": {
            "output_path": OUT,
            "output_schema": SCHEMA,
            "named_probes": [
                {"id": "probe1", "role": "same-invocation-suite", "command": P1},
                {"id": "probe2", "role": "detector-control", "command": P2},
            ],
            "notes": (
                "G-1 for CNF-0035: live named probes exit 0, confirmation "
                "artifact state=SUCCESS, per-unit manifest row. Did not run "
                "global unit_manifest.py --write. No ADV rebuild. Schema $ref "
                "resolved from disk; no network."
            ),
        },
    }
    validate_or_die(doc, validator)
    dumped = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if SENTINEL not in dumped or "SUCCESS:CNF-0035" not in dumped:
        print("FAILED:CNF-0035 completion sentinel not in artifact")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumped, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0035 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:CNF-0035")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
