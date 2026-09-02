#!/usr/bin/env python3
"""Offline jsonschema validation for ADV-0129's catalog shim (no network).

jsonschema 4.10 on this box follows $ref with requests.get(). The catalog
shim points at https://ast-integrate.invalid/... which does not resolve.
This store maps those $id URLs onto the on-disk physical schemas.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/calibration-report.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"
GARBAGE = (
    {},
    {"unit_id": "ADV-0129", "passing_tests": 999999},
    {"blob": "x" * 2000, "state": "SUCCESS"},
    {"report_kind": "not-calibration"},
)


def _load(rel: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not doc.get("$id"):
        raise ValueError(f"{rel} missing $id")
    return doc


def offline_validator():
    shim = _load(SHIM)
    profiles = _load(PROFILES)
    receipt = _load(RECEIPT)
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = jsonschema.RefResolver(
        base_uri=str(shim["$id"]),
        referrer=shim,
        store=store,
    )
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def payload(doc: dict) -> dict:
    """Top-level receipt fields plus report.* domain payload."""
    out = dict(doc)
    report = doc.get("report")
    if isinstance(report, dict):
        out.update(report)
    return out


def errors_for(instance: object) -> list[str]:
    out = []
    for err in offline_validator().iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_rejected() -> bool:
    for probe in GARBAGE:
        if not errors_for(probe):
            return False
    return True


if __name__ == "__main__":
    v = offline_validator()
    if not garbage_rejected():
        raise SystemExit("FAILED:ADV-0129 schema_offline accepted garbage")
    print(f"ok validator={type(v).__name__} garbage_rejected=true")
