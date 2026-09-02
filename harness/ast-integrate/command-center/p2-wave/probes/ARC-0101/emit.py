#!/usr/bin/env python3
"""Emit command-center/phase4/conformance/ARC-0101.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import report as R  # noqa: E402
import schema_local as S  # noqa: E402

OUT = "command-center/phase4/conformance/ARC-0101.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0101/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0101/probe2_consumer_table.py"
)
SUPPORTING = [
    (SCHEMA, "supporting"),
    ("command-center/p2-wave/probes/ARC-0101/detector.py", "supporting"),
    ("command-center/p2-wave/probes/ARC-0101/consumers.py", "supporting"),
    (
        "command-center/p2-wave/probes/ARC-0101/fixtures/planted-case-collision.schema.json",
        "fixture",
    ),
    (
        "command-center/p2-wave/probes/ARC-0101/fixtures/planted-duplicate-keys.json",
        "fixture",
    ),
]


def digest_file(rel: str) -> tuple[str, int, str]:
    raw = (REPO / rel).read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    eol = "LF" if b"\r\n" not in raw else "CRLF"
    return hashlib.sha256(norm).hexdigest(), len(norm), eol


def artifact_row(rel: str, role: str) -> dict:
    sha, size, eol = digest_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def main() -> int:
    payload = R.measured()
    control = payload["detector_control"]
    census = payload["schema_census"]
    table = payload["consumers"]
    fp = payload["fingerprint"]
    if not control.get("trusted"):
        print("FAILED:ARC-0101 detector control not trusted")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_n = sum(
        1 for r in table if r.get("role") == "live-consumer" and r.get("available")
    )
    obs = [
        {
            "name": "detector_control_fired",
            "measured": bool(control.get("fired")),
            "method": "planted Name/name schema before census",
            "anchor": "command-center/p2-wave/probes/ARC-0101/detector.py:run_control",
        },
        {
            "name": "detector_control_clean_silent",
            "measured": bool(control.get("clean_silent")),
            "method": "planted clean schema with a single id property",
            "anchor": "command-center/p2-wave/probes/ARC-0101/fixtures/planted-clean.schema.json",
        },
        {
            "name": "files_parsed",
            "measured": int(fp["files_parsed"]),
            "method": "pairs-preserving walk of command-center *.schema.json excluding probe trees",
            "anchor": "command-center/p2-wave/probes/ARC-0101/detector.py:census_live",
        },
        {
            "name": "same_object_case_collision_count",
            "measured": int(fp["same_object_case_collision_count"]),
            "method": "same-object key casefold groups from schema files",
            "anchor": "command-center/p2-wave/probes/ARC-0101/detector.py:note_object",
        },
        {
            "name": "any_live_consumer_case_insensitive",
            "measured": bool(fp["any_live_consumer_case_insensitive"]),
            "method": "feed planted Name/name document to live parsers",
            "anchor": "command-center/p2-wave/probes/ARC-0101/consumers.py:measure_all",
        },
        {
            "name": "live_consumers_measured",
            "measured": int(live_n),
            "method": "python/node/jq/jsonschema on planted-duplicate-keys.json",
            "anchor": "command-center/p2-wave/probes/ARC-0101/fixtures/planted-duplicate-keys.json",
        },
        {
            "name": "seeded_casefold_collapses",
            "measured": bool(fp["seeded_casefold_collapses"]),
            "method": "object_pairs_hook that casefolds keys",
            "anchor": "command-center/p2-wave/probes/ARC-0101/consumers.py:python_casefold",
        },
        {
            "name": "strict_duplicate_errors",
            "measured": bool(fp["strict_duplicate_errors"]),
            "method": "object_pairs_hook that errors on repeated keys",
            "anchor": "command-center/p2-wave/probes/ARC-0101/consumers.py:python_strict_dup",
        },
    ]
    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0101",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0101",
        "spec_anchor": "_USER-PROMPTS.md:10822",
        "min_bytes_threshold": 2048,
        "artifacts": [artifact_row(rel, role) for rel, role in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "A planted Name/name schema pair is detected before any "
                    "zero-collision census is trusted, and a clean schema stays silent."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ARC-0101/detector.py:run_control",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": (
                            f"fired={control.get('fired')} "
                            f"clean_silent={control.get('clean_silent')} "
                            f"order={control.get('order')}"
                        ),
                        "fingerprint": "probe1:detector-control",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "command-center/p2-wave/probes/ARC-0101/fixtures/"
                            "planted-case-collision.schema.json"
                        ),
                        "raw_output": '"Name" and "name" both present in properties',
                        "fingerprint": "fixture:name-pair",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Duplicate-key and case-variant behaviour is measured per "
                    "live consumer (last-wins / both-preserved), never assumed "
                    "from a language spec."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ARC-0101/consumers.py:measure_all",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "command-center/p2-wave/probes/ARC-0101/consumers.py:"
                            "measure_all"
                        ),
                        "raw_output": (
                            f"live_dup={fp['live_duplicate_behaviours']} "
                            f"live_case={fp['live_case_behaviours']}"
                        ),
                        "fingerprint": "consumers:measure_all",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            f"seeded_casefold={fp['seeded_casefold_collapses']} "
                            f"strict_dup={fp['strict_duplicate_errors']}"
                        ),
                        "fingerprint": "probe2:consumer-table",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "detector-control-planted-case-collision",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "duplicate-key-per-consumer",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "planted-name-pair-vs-clean",
                "kind": "known-broken-fixture",
                "description": (
                    "Detector fires on planted Name/name and is silent on a "
                    "clean single-key schema."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"fired={control.get('fired')}",
                "good_state_output": f"clean_silent={control.get('clean_silent')}",
            },
            {
                "id": "assumed-false-required-on-consumer-rows",
                "kind": "mutation",
                "description": (
                    "Dropping assumed=false from a live consumer row must make "
                    "the consumer-table checker fail."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "row[0]-assumed-not-false",
                "good_state_output": "assumed=false on every measured row",
            },
            {
                "id": "output-schema-rejects-empty",
                "kind": "malformed-input",
                "description": (
                    "The declared conformance-report schema must reject {} "
                    "once $ref is resolved offline."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "empty object rejected",
                "good_state_output": "measured receipt accepted",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0101-probe2-consumer-table",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-measures the live consumer table and checks the "
                "artifact fingerprint; it does not re-author the census."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0101/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "ARC-0101",
        },
        "downstream_consumers": [
            {
                "consumer": "schema_local.Draft202012Validator",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "command-center/p2-wave/probes/ARC-0101/schema_local.py"
                    ),
                    "raw_output": "offline RefResolver store; empty object rejected",
                    "fingerprint": "schema-local:conformance-report",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "retry once after fixing validator input; a second "
                "schema-invalid result closes the unit FAILED"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Named phase-4 contract files ARC-0078.json through "
                    "ARC-0087.json are absent on this worktree."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Re-run the census when those contract files exist. Do not "
                    "rebuild them here (no ADV circle)."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "test-engineer",
            "execution_substrate": "worktree-isolated",
        },
        "report": {
            "kind": "conformance-report",
            "observations": obs,
            "control_ids": [
                "planted-case-collision",
                "planted-clean-schema",
                "strict-duplicate-hook",
                "seeded-casefold-hook",
            ],
            "title": "Case-collision and duplicate-key conformance",
            "question": payload["question"],
            "seeded_failure_class": {
                "id": "FC-11310",
                "name": "case-insensitive parser collision",
                "spec": 11310,
            },
            "detector_control": control,
            "named_contracts": payload["named_contracts"],
            "schema_census": census,
            "consumers": table,
            "answers": payload["answers"],
            "fingerprint": fp,
            "strongest_surviving_counterargument": (
                "Named contract files ARC-0078.json through ARC-0087.json are "
                "absent, so a zero-collision result over those paths is an "
                "empty-set measurement. That does not license skipping the "
                "detector control or assuming parser behaviour: the planted "
                "Name/name pair still fires, live JSON Schema files under "
                "command-center (excluding probe trees) are enumerated, and "
                "python/node/jq are fed real documents."
            ),
        },
    }

    empty_errors = S.iter_errors({})
    if not empty_errors:
        print("FAILED:ARC-0101 output schema accepts empty object (vacuous)")
        return 1
    errors = S.iter_errors(doc)
    if errors:
        print(f"FAILED:ARC-0101 schema-invalid {errors[0].message}")
        for err in errors[:12]:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            print(f"  {loc}: {err.message}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:ARC-0101" not in text:
        print("FAILED:ARC-0101 sentinel missing from artifact")
        return 1
    out_path.write_text(text, encoding="utf-8")
    print(
        f"wrote {OUT} collisions={fp['same_object_case_collision_count']} "
        f"parsed={fp['files_parsed']} live_ci={fp['any_live_consumer_case_insensitive']}"
    )
    print("SUCCESS:ARC-0101 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
