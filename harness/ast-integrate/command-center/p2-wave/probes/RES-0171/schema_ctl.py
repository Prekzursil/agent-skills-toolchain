#!/usr/bin/env python3
"""Offline validator for command-center/schema/design-spec.schema.json.

The shim $ref targets https://ast-integrate.invalid/... which has no DNS.
jsonschema 4.10 on this box still uses RefResolver (not referencing.Registry),
so populate a disk store and never fetch. Do not rebuild the generated shim.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/design-spec.schema.json"
SHIM_URI = "https://ast-integrate.invalid/command-center/schema/design-spec.schema.json"
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
        raise AssertionError("schema rejected document: " + "; ".join(errs[:12]))


def domain_payload(doc: dict) -> dict:
    """Return the design payload (report) or the document itself."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        "cache_key" in report or "staleness_policy" in report or "both_states" in report
    ):
        return report
    return doc


def garbage_rejected() -> list[str]:
    """Return error lists that must be non-empty for each garbage document."""
    samples = (
        {},
        {"unit_id": "nope", "state": "SUCCESS"},
        {"unit_id": "RES-0171", "state": "SUCCESS"},
        {
            "schema_version": 1,
            "unit_id": "RES-0171",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:RES-0171",
            "spec_anchor": "catalog",
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
            "retry": {"count": 0, "policy": "two strikes then pivot"},
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
                "kind": "not-a-design-spec",
                "observations": [
                    {"name": "n", "measured": 1, "method": "m", "anchor": "a"}
                ],
                "control_ids": ["c1"],
            },
        },
    )
    counts = []
    for garbage in samples:
        errs = errors(garbage)
        if not errs:
            raise AssertionError(f"schema accepted garbage keys={list(garbage)[:6]}")
        counts.append(len(errs))
    return counts
