"""Disk-only jsonschema validator for the catalog council-simulation-spec shim.

jsonschema 4.10 Draft7Validator otherwise follows $id to
https://ast-integrate.invalid/... (network). Map those $id values onto the
files that already exist under platform/schema/.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = REPO / "command-center/schema/council-simulation-spec.schema.json"
PROFILES = REPO / "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = REPO / "platform/schema/receipt.schema.json"


def catalog_validator() -> Draft7Validator:
    shim = json.loads(SHIM.read_text(encoding="utf-8"))
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    store = {}
    for doc in (shim, profiles, receipt):
        ident = doc.get("$id")
        if ident:
            store[ident] = doc
    resolver = RefResolver.from_schema(shim, store=store)
    return Draft7Validator(shim, resolver=resolver)


def results_section(doc: dict) -> dict:
    if isinstance(doc.get("results"), dict):
        return doc["results"]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report.get("results"), dict):
        return report["results"]
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    if isinstance(ext.get("results"), dict):
        return ext["results"]
    return {}


def negative_control_section(doc: dict) -> dict:
    if isinstance(doc.get("negative_control"), dict):
        return doc["negative_control"]
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    if isinstance(ext.get("negative_control"), dict):
        return ext["negative_control"]
    return {}
