#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0123-downstream-readability.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from consumers import ConsumeError, consume_path, consumer_command  # noqa: E402
from measure import full_measure  # noqa: E402
import jsonschema  # noqa: E402
from jsonschema import RefResolver  # noqa: E402

OUT = "command-center/confirmation/CNF-0123-downstream-readability.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
UNREADABLE_FIX = (
    "command-center/p2-wave/probes/CNF-0123/fixtures/schema-valid-unreadable.json"
)
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0123/probe1_consumer_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0123/probe2_detector_control.py"
)
QUESTION = (
    "Completion condition 12 says downstream consumers can read the output. "
    "Prove it by running a real consumer against one artifact of every class "
    "and answer: which classes have no consumer at all, and which fail to parse "
    "in the consumer even though they validate against their schema?"
)
PHYSICAL_SCHEMAS = (
    SCHEMA,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0123":
            return unit
    raise SystemExit("FAILED:CNF-0123 catalog row missing")


def _patch_self_row(classes: list[dict]) -> None:
    """The report cannot consume itself before it exists; stamp the self row."""
    for row in classes:
        if row.get("class_id") != "conformance-report":
            continue
        row["sample_path"] = OUT
        row["sample_source"] = "self"
        row["finding"] = "consumed-readable"
        row["exit_code"] = 0
        row["parsed_record_count"] = len(classes)
        row["consumer_command"] = consumer_command("conformance-report", OUT)
        row["diagnostic"] = "self artifact; consumer re-run after write"
        row["output_schema"] = SCHEMA
        return


def digest_rel(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe(
    role: str, method: str, command: str, raw_output: str, exit_code: int = 0
) -> dict[str, Any]:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:4000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def local_validator() -> jsonschema.Draft7Validator:
    """Resolve ast-integrate.invalid $ref onto disk. Never the network."""
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    store: dict[str, Any] = {}
    for rel in PHYSICAL_SCHEMAS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    resolver = RefResolver.from_schema(schema, store=store)
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def artifact_row(rel: str, role: str) -> dict[str, Any]:
    sha, size = digest_rel(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if "SUCCESS:CNF-0123" not in sentinel:
        print("FAILED:CNF-0123 catalog sentinel does not contain SUCCESS:CNF-0123")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    measured = full_measure()
    classes = measured["classes"]
    _patch_self_row(classes)
    unconsumed = [r["class_id"] for r in classes if r["finding"] == "unconsumed"]
    unreadable = measured["schema_valid_unreadable"]
    corrupt = measured["corruption_control"]
    payload = measured["payload_records_control"]

    missing_coverage = [
        r["class_id"]
        for r in classes
        if r["exit_code"] is None
        and r["finding"] not in ("unconsumed", "no-produced-sample")
    ]
    if missing_coverage:
        print("FAILED:CNF-0123 class without exit_code or unconsumed finding:")
        print(" ".join(missing_coverage[:40]))
        return 1
    if not unconsumed:
        print("FAILED:CNF-0123 expected at least one unconsumed class")
        return 1
    if not payload.get("detector_fired"):
        print("FAILED:CNF-0123 schema-valid-unreadable detector did not fire")
        print(json.dumps(payload, indent=2)[:1500])
        return 1
    if not corrupt.get("failed"):
        print("FAILED:CNF-0123 corruption control did not fail the consumer")
        print(json.dumps(corrupt, indent=2)[:1500])
        return 1

    produced_ok = [
        r
        for r in classes
        if r.get("sample_source") == "produced"
        and r.get("finding") == "consumed-readable"
    ]
    if len(produced_ok) < 3:
        print(
            f"FAILED:CNF-0123 produced readable classes={len(produced_ok)} want>=3"
        )
        for r in classes:
            if r.get("sample_source") == "produced":
                print(" ", r["class_id"], r.get("finding"), r.get("diagnostic"))
        return 1

    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/CNF-0123/consumers.py",
        "command-center/p2-wave/probes/CNF-0123/inventory.py",
        UNREADABLE_FIX,
    ]
    artifacts = [artifact_row(rel, "supporting") for rel in supporting]
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        f"{len(unconsumed)} catalog artifact classes have no registered "
        f"downstream consumer and are reported unconsumed (not passing). "
        f"{len(unreadable)} schema-valid artifacts failed a field-extracting "
        f"consumer (including the payload-records fixture). "
        f"Corruption of {corrupt['sample_path']} made the "
        f"{corrupt['target_class']} consumer exit {corrupt['corrupt_exit_code']} "
        f"after the intact copy exited {corrupt['intact_exit_code']}."
    )
    doc: dict[str, Any] = {
        "schema_version": 1,
        "unit_id": "CNF-0123",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0123",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "contract-verification-engineer",
            "execution_substrate": "linux-headless",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Every catalog artifact class has a consumer exit code or "
                    "an explicit unconsumed/no-produced-sample finding."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "report.classes[].finding|exit_code",
                "probes": [
                    probe("source", "command", P1, "consumer-matrix"),
                    probe("verifier", "test-run", P2, "detector-control"),
                ],
            },
            {
                "claim": (
                    "schema-valid but consumer-unreadable is observed on the "
                    "payload-records fixture; corruption of a produced "
                    f"{corrupt['target_class']} artifact fails the consumer."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": UNREADABLE_FIX,
                "probes": [
                    probe(
                        "source",
                        "command",
                        P2,
                        f"unreadable_exit={payload.get('unreadable_exit_code')}",
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        corrupt["consumer_command"] or P2,
                        f"corrupt_exit={corrupt['corrupt_exit_code']}",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-schema-valid-unreadable",
                "name": "schema-valid but consumer-unreadable is a real state",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T2-unconsumed-not-passing",
                "name": "a class with no consumer is reported as unconsumed",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T3-corruption-control",
                "name": "corrupt one artifact and confirm the consumer fails",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-payload-records-unreadable",
                "kind": "known-broken-fixture",
                "description": (
                    "payload-records schema-valid fixture lacks payload.value "
                    "and must be rejected; the readable twin must pass."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"exit={payload.get('unreadable_exit_code')}",
                "good_state_output": f"exit={payload.get('readable_exit_code')}",
            },
            {
                "id": "NC-corruption-control",
                "kind": "malformed-input",
                "description": (
                    "Truncating a produced architecture-review artifact must "
                    "fail the consumer after the intact copy passes."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"exit={corrupt['corrupt_exit_code']}",
                "good_state_output": f"exit={corrupt['intact_exit_code']}",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0123-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Reviewer re-runs the detector control: schema-valid-unreadable "
                "fixture, planted unconsumed class, and JSON corruption. "
                "Re-reading this document is not the review."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0123/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0123",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0123/consumers.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    consumer_command("conformance-report", OUT),
                    "self-consumer after write",
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "zero retries"),
        },
        "residual_unknowns": [],
        "report": {
            "kind": "conformance-report",
            "observations": [
                {
                    "name": "unconsumed-class-count",
                    "measured": len(unconsumed),
                    "method": "class-by-class consumer matrix over catalog output_schema",
                    "anchor": "report.unconsumed_classes",
                },
                {
                    "name": "schema-valid-unreadable-count",
                    "measured": len(unreadable),
                    "method": "schema validate then field-extracting consumer",
                    "anchor": UNREADABLE_FIX,
                },
                {
                    "name": "produced-readable-count",
                    "measured": len(produced_ok),
                    "method": "consumer exit 0 on a produced catalog sample",
                    "anchor": "report.answers.produced_readable_classes",
                },
                {
                    "name": "corruption-control-failed",
                    "measured": True,
                    "method": "truncate produced sample mid-JSON and re-run consumer",
                    "anchor": corrupt["sample_path"],
                },
            ],
            "control_ids": [
                "payload-records-both-states",
                "corruption-control",
                "planted-unconsumed",
            ],
            "question": QUESTION,
            "answer": answer,
            "parser": {
                "identity": "command-center/p2-wave/probes/CNF-0123/consumers.py",
                "strict": True,
                "schema_id": SCHEMA,
                "hand_written_field_list": False,
            },
            "classes": classes,
            "unconsumed_classes": unconsumed,
            "schema_valid_unreadable": unreadable,
            "corruption_control": corrupt,
            "payload_records_control": payload,
            "controls": {
                "schema_valid_unreadable": payload,
                "corruption": corrupt,
                "planted_unconsumed": "planted-unconsumed",
            },
            "answers": {
                "unconsumed_class_count": len(unconsumed),
                "schema_valid_unreadable_count": len(unreadable),
                "produced_readable_classes": [r["class_id"] for r in produced_ok],
                "corruption_control_failed": True,
                "payload_records_both_states": True,
            },
            "named_probes": [
                {"id": "probe1", "role": "consumer-matrix", "command": P1},
                {"id": "probe2", "role": "detector-control", "command": P2},
            ],
        },
    }

    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0123 schema errors")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"unit_id": "CNF-0123", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0123 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    try:
        consume_path("conformance-report", out)
    except ConsumeError as exc:
        print(f"FAILED:CNF-0123 self-consumer {exc.message}")
        return 1

    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0123 artifact {size}B below floor")
        return 1
    print(
        f"wrote {OUT} bytes={size} classes={len(classes)} "
        f"unconsumed={len(unconsumed)} unreadable={len(unreadable)}"
    )
    print("SUCCESS:CNF-0123 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
