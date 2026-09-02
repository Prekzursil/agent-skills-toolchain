#!/usr/bin/env python3
"""Offline validator for command-center/schema/reproducibility-report.schema.json.

The catalog file is a generated $ref shim whose $id lives under
https://ast-integrate.invalid/... which has no DNS. jsonschema 4.10 on this
box still uses RefResolver, so populate a disk store and never fetch.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/reproducibility-report.schema.json"
SHIM_URI = (
    "https://ast-integrate.invalid/command-center/schema/reproducibility-report.schema.json"
)
STORE_FILES = {
    SHIM_URI: REPO / SCHEMA_REL,
    "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": (
        REPO / "platform/schema/artifact-class-profiles.schema.json"
    ),
    "https://ast-integrate.invalid/platform/schema/receipt.schema.json": (
        REPO / "platform/schema/receipt.schema.json"
    ),
}


def load_store() -> dict:
    store = {}
    for uri, path in STORE_FILES.items():
        store[uri] = json.loads(path.read_text(encoding="utf-8"))
    return store


def validator() -> Draft202012Validator:
    store = load_store()
    schema = store[SHIM_URI]
    resolver = RefResolver(base_uri=SHIM_URI, referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def errors(doc) -> list[str]:
    out = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def assert_valid(doc) -> None:
    errs = errors(doc)
    if errs:
        raise AssertionError("schema rejected document: " + "; ".join(errs[:8]))


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Unit payload lives under report; fall back to the envelope."""
    report = doc.get("report")
    return report if isinstance(report, dict) else doc


def garbage_rejected() -> None:
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 200},
        {"unit_id": "SYN-0038", "state": "SUCCESS"},
        {
            "schema_version": 1,
            "unit_id": "SYN-0038",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:SYN-0038",
            "spec_anchor": "x" * 8,
            "min_bytes_threshold": 1,
            "artifacts": [
                {
                    "path": "a",
                    "bytes": 1,
                    "sha256": "a" * 64,
                    "exists": True,
                }
            ],
            "evidence": [
                {
                    "claim": "c",
                    "verdict": "NOT-CHECKED",
                    "anchor": "a",
                    "probes": [
                        {
                            "role": "source",
                            "method": "file-read",
                            "command": "x",
                            "raw_output": "y",
                            "fingerprint": "z",
                        }
                    ],
                }
            ]
            * 2,
            "timestamps": {
                "started_at": "2026-08-25T00:00:00Z",
                "ended_at": "2026-08-25T00:00:00Z",
            },
            "retry": {"count": 0, "policy": "zero retries first observation is verdict"},
            "tests": [{"id": "t", "command": "c", "result": "PASS"}],
            "negative_controls": [
                {
                    "id": "n",
                    "kind": "mutation",
                    "description": "d",
                    "fired_on_bad_state": True,
                    "silent_on_good_state": True,
                }
            ],
            "reviewer": {
                "reviewer_id": "r",
                "verdict": "PASS",
                "independent": True,
            },
            "manifest_registration": {"registered": True, "manifest_path": "m"},
            "downstream_consumers": [
                {
                    "consumer": "c",
                    "artifact_path": "p",
                    "executed": True,
                    "read_ok": True,
                    "probe": {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": "x",
                        "raw_output": "y",
                        "fingerprint": "q",
                    },
                }
            ],
            "residual_unknowns": [
                {
                    "claim": "c",
                    "verdict": "NOT-CHECKED",
                    "settling_experiment": "s",
                }
            ],
            "report": {
                "kind": "not-a-reproducibility-report",
                "observations": [
                    {"name": "n", "measured": 1, "method": "m", "anchor": "a"}
                ],
                "control_ids": ["c1"],
            },
        },
    ):
        if not errors(garbage):
            raise AssertionError(f"schema accepted garbage keys={list(garbage)[:6]}")
