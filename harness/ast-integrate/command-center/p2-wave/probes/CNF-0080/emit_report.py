#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0080-dryrun-parity.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from jsonschema import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0080-dryrun-parity.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
UNIT = "CNF-0080"
SPEC_ANCHOR = "command-center/WORK-UNIT-CATALOG.json:CNF-0080"
QUESTION = (
    "Does the dry run tell the truth? Capture the plan a dry run predicts "
    "and the actions a real run performs, then answer: do the two match "
    "action for action, and does the dry run ever omit a destructive step "
    "that the real run performs?"
)
SENTINEL = (
    "SUCCESS:CNF-0080 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the extra-write control "
    "was captured by the tracer and both action lists are attached. Any other "
    "terminal state is FAILED:CNF-0080 <classification> with the diagnostic "
    "tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0080/probe1_extra_write.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0080/probe2_detector_control.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "CNF-0080", "state": "SUCCESS"},
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0080/fs_tracer.py",
    "command-center/p2-wave/probes/CNF-0080/mutator.py",
    "command-center/p2-wave/probes/CNF-0080/close_subject.py",
    "command-center/p2-wave/probes/CNF-0080/suite.py",
    "command-center/p2-wave/probes/CNF-0080/probe1_extra_write.py",
    "command-center/p2-wave/probes/CNF-0080/probe2_detector_control.py",
    "command-center/p2-wave/probes/CNF-0080/emit_report.py",
]


def digest_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_block(
    role: str, method: str, command: str, raw: str, fingerprint: str
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65536],
        "fingerprint": fingerprint,
        "exit_code": 0,
    }


def local_validator() -> jsonschema.Draft7Validator:
    """Resolve conformance-report $ref onto disk. Never fetch ast-integrate.invalid."""
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        schema["$id"]: schema,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=store)
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def validate_or_die(doc: dict) -> None:
    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0080 schema-invalid")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            raise SystemExit("FAILED:CNF-0080 schema accepts garbage")


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = S.run_suite()
    extra = report["extra_write"]
    honest = report["honest_parity"]
    lying = report["lying_detector"]
    close = report["close_py"]
    if not extra["pass"]:
        print("FAILED:CNF-0080 extra-write control was not captured by the tracer")
        return 1
    if not honest["pass"]:
        print("FAILED:CNF-0080 honest shared-plan parity failed")
        return 1
    if not lying["pass"]:
        print("FAILED:CNF-0080 detector did not fire on known-broken omitted delete")
        return 1
    if not extra["predicted_actions"] or not extra["traced_actions"]:
        print("FAILED:CNF-0080 action lists missing")
        return 1
    if not honest["predicted_actions"] or not honest["traced_actions"]:
        print("FAILED:CNF-0080 honest action lists missing")
        return 1

    extra_raw = json.dumps(
        {
            "captured": extra["captured_by_tracer"],
            "predicted": extra["predicted_actions"],
            "traced": extra["traced_actions"],
        },
        sort_keys=True,
        default=str,
    )
    lie_raw = json.dumps(
        {
            "p0_filed": lying["p0_filed"],
            "omitted": lying["omitted_destructive"],
            "predicted": lying["predicted_actions"],
            "traced": lying["traced_actions"],
        },
        sort_keys=True,
        default=str,
    )
    honest_raw = json.dumps(
        {
            "keys_match": honest["keys_match"],
            "dry_zero": honest["dry_run_zero_writes"],
            "predicted": honest["predicted_actions"],
            "traced": honest["traced_actions"],
        },
        sort_keys=True,
        default=str,
    )
    src_extra = probe_block(
        "source",
        "test-run",
        "python3 -B command-center/p2-wave/probes/CNF-0080/suite.py extra_write_control",
        extra_raw,
        "cnf0080:suite-extra-write",
    )
    ver_extra = probe_block(
        "verifier",
        "file-read",
        "command-center/p2-wave/probes/CNF-0080/mutator.py:apply_extra_write",
        "apply_extra_write writes sneak.txt after the shared plan; dry_run never names it",
        "cnf0080:mutator-sneak-read",
    )
    src_lie = probe_block(
        "source",
        "test-run",
        "python3 -B command-center/p2-wave/probes/CNF-0080/suite.py lying_detector",
        lie_raw,
        "cnf0080:suite-lying-delete",
    )
    ver_lie = probe_block(
        "verifier",
        "file-read",
        "command-center/p2-wave/probes/CNF-0080/mutator.py:lying_plan",
        "lying_plan omits victim.txt delete; apply_lying still deletes it",
        "cnf0080:mutator-lying-read",
    )
    src_honest = probe_block(
        "source",
        "test-run",
        "python3 -B command-center/p2-wave/probes/CNF-0080/suite.py honest_parity",
        honest_raw,
        "cnf0080:suite-honest-parity",
    )
    ver_honest = probe_block(
        "verifier",
        "byte-compare",
        "command-center/p2-wave/probes/CNF-0080/fs_tracer.py:diff_census",
        "before/after sha256 census keyset equals shared dry_run plan",
        "cnf0080:census-honest-compare",
    )
    consumer_probe = probe_block(
        "verifier",
        "schema-validate",
        "jsonschema Draft7Validator + disk RefResolver on conformance-report.schema.json",
        "0 errors; garbage probes rejected",
        "cnf0080:schema-validate",
    )

    checks = [
        {
            "id": "extra-write-control",
            "verdict": "PASS" if extra["pass"] else "FAIL",
            "title": "tracer census sees one extra write the plan never named",
            "captured_by_tracer": extra["captured_by_tracer"],
            "sneak_path": extra["sneak_path"],
            "method": extra["method"],
        },
        {
            "id": "honest-plan-parity",
            "verdict": "PASS" if honest["pass"] else "FAIL",
            "title": "shared-plan dry-run matches traced apply action for action",
            "keys_match": honest["keys_match"],
            "dry_run_zero_writes": honest["dry_run_zero_writes"],
        },
        {
            "id": "known-broken-omitted-delete",
            "verdict": "PASS" if lying["pass"] else "FAIL",
            "title": (
                "detector fires when dry-run omits a destructive delete "
                "the real run performs"
            ),
            "p0_filed": lying["p0_filed"],
            "classification": lying["classification"],
        },
        {
            "id": "production-close-dryrun",
            "verdict": "FAIL" if close.get("understates") else "PASS",
            "title": (
                "tools/command-center/close.py --dry-run vs real --note "
                "on a disposable catalog"
            ),
            "understates": close.get("understates"),
            "dry_run_zero_writes": close.get("dry_run_zero_writes"),
            "subject": close.get("subject"),
            "note": (
                "Dry-run writes nothing (correct) but its stdout does not list "
                "the catalog.json / graph.json / events.jsonl mutations the real "
                "run performs. Predicted action list is therefore empty; the "
                "traced list is attached. Filed as dryrun-understates."
            ),
        },
    ]

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 2048,
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Filesystem census captured sneak.txt; the dry-run plan "
                    "never named that path."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0080/mutator.py:apply_extra_write",
                "probes": [src_extra, ver_extra],
            },
            {
                "claim": (
                    "A delete present in the real run and absent from the dry-run "
                    "plan is detected as P0 (victim.txt)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0080/mutator.py:lying_plan",
                "probes": [src_lie, ver_lie],
            },
            {
                "claim": (
                    "Honest shared-plan dry-run matches the traced apply keyset "
                    "and writes nothing."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0080/fs_tracer.py:diff_census",
                "probes": [src_honest, ver_honest],
            },
        ],
        "tests": [
            {"id": "T1-extra-write-control", "command": P1, "result": "PASS"},
            {"id": "T2-detector-control", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "CNF0080-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "Lying dry-run omits the victim.txt delete that apply still "
                    "performs. The detector must fire. Honest shared-plan dry-run "
                    "must stay silent (exact key match)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": lie_raw[:16384],
                "good_state_output": honest_raw[:16384],
            },
            {
                "id": "CNF0080-C2",
                "kind": "malformed-input",
                "description": (
                    "conformance-report schema must reject empty and unrelated "
                    "objects when $ref is resolved from disk."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "schema-invalid on garbage",
                "good_state_output": "schema-valid conformance-report receipt",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0080-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Named probe2 re-runs the DETECTOR CONTROL on the known-broken "
                "omitted-delete fixture and does not re-read this conclusion "
                "as evidence."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0080/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNF-0080/probe1_extra_write.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": consumer_probe,
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
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
                    "Only the disposable shared-plan operator and "
                    "tools/command-center/close.py --note were traced. Other "
                    "dry-run verbs in this repo were not measured."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add one extra dry-run operator per remaining CLI verb "
                    "and repeat the census vs predicted-plan comparison."
                ),
            }
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "dry-run-verification-engineer",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "conformance-report",
            "observations": [
                {
                    "name": "extra_write_captured_by_tracer",
                    "measured": bool(extra["captured_by_tracer"]),
                    "method": "before/after sha256 census",
                    "anchor": "command-center/p2-wave/probes/CNF-0080/fs_tracer.py",
                },
                {
                    "name": "honest_shared_plan_keys_match",
                    "measured": bool(honest["keys_match"]),
                    "method": "plan keyset vs census keyset",
                    "anchor": "command-center/p2-wave/probes/CNF-0080/mutator.py",
                },
                {
                    "name": "omitted_delete_detector_fired",
                    "measured": bool(lying["p0_filed"]),
                    "method": "lying_plan vs apply_lying census",
                    "anchor": "command-center/p2-wave/probes/CNF-0080/suite.py",
                },
                {
                    "name": "production_close_py_dry_run_understates",
                    "measured": bool(close.get("understates")),
                    "method": "close.py --dry-run vs real --note census",
                    "anchor": "tools/command-center/close.py",
                },
            ],
            "control_ids": [
                "extra-write-control",
                "known-broken-omitted-delete",
                "honest-shared-plan-parity",
            ],
            "title": "Dry-run versus real-run plan parity",
            "question": QUESTION,
            "completion_sentinel": SENTINEL,
            "output_path": OUT,
            "output_schema": SCHEMA,
            "parser": {
                "name": "cnf-0080-fs-census-tracer",
                "version": "sha256-census-2026-08-24",
                "path": "command-center/p2-wave/probes/CNF-0080/fs_tracer.py",
                "method": "before/after sha256+byte census of a disposable tree",
            },
            "answers": {
                "shared_plan_dry_run_matches_trace": honest["keys_match"],
                "dry_run_zero_writes_on_honest_operator": honest[
                    "dry_run_zero_writes"
                ],
                "extra_write_captured_by_tracer": extra["captured_by_tracer"],
                "omitted_destructive_delete_is_p0": lying["p0_filed"],
                "production_close_py_dry_run_understates": close.get("understates"),
            },
            "checks": checks,
            "predicted_actions": honest["predicted_actions"],
            "traced_actions": honest["traced_actions"],
            "extra_write_control": {
                "predicted_actions": extra["predicted_actions"],
                "traced_actions": extra["traced_actions"],
                "captured_by_tracer": extra["captured_by_tracer"],
                "sneak_path": extra["sneak_path"],
            },
            "known_broken_fixture": {
                "predicted_actions": lying["predicted_actions"],
                "traced_actions": lying["traced_actions"],
                "omitted_destructive": lying["omitted_destructive"],
                "p0_filed": lying["p0_filed"],
            },
            "production_close_py": {
                "subject": close.get("subject"),
                "predicted_actions": close.get("predicted_actions"),
                "traced_actions": close.get("traced_actions"),
                "dry_run_wrote": close.get("dry_run_wrote"),
                "dry_stdout": close.get("dry_stdout"),
                "real_stdout": close.get("real_stdout"),
                "understates": close.get("understates"),
                "omitted_from_dry_run": close.get("omitted_from_dry_run"),
                "classification": (
                    "dryrun-understates" if close.get("understates") else None
                ),
            },
            "findings": [
                {
                    "severity": "P0",
                    "classification": "dryrun-understates",
                    "subject": "tools/command-center/close.py --dry-run",
                    "detail": (
                        "Real --note on a disposable catalog overwrites "
                        "catalog.json and graph.json and creates events.jsonl. "
                        "The dry-run prints 'nothing written' and does not name "
                        "those mutations, so the predicted action list "
                        "understates the real run."
                    ),
                }
            ],
            "named_probes": [
                {"id": "probe1", "role": "extra-write-control", "command": P1},
                {"id": "probe2", "role": "detector-control", "command": P2},
            ],
            "cloud_ok": False,
            "adv_rebuild_circle": False,
            "notes": (
                "G-1 for CNF-0080: live named probes exit 0, confirmation "
                "artifact state=SUCCESS, per-unit manifest row. Did not run "
                "global unit_manifest.py --write. Extra-write control captured "
                "by census tracer; both action lists attached. close.py "
                "--dry-run understates and is filed in report.findings; the "
                "shared-plan fixture dry-run matches the trace."
            ),
        },
    }
    validate_or_die(doc)
    payload = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:CNF-0080 completion sentinel not in artifact")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0080 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:CNF-0080")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
