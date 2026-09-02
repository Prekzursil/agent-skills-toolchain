#!/usr/bin/env python3
"""Probe 1: constraint-syntax classification per declaration.

Named classes: exact, compatible, caret, tilde, wildcard, none.
Planted fixtures must hit all six; live tree is classified independently.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL
SCHEMA = L.REPO / L.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0025-probe1 {msg}")
    return 1


def main() -> int:
    payload = L.probe1_payload()
    print(L.dumps(payload))
    clf = payload["classifier_control"]
    if clf["missing"] or clf["wrong"]:
        return fail(f"fixture classification {clf}")
    if not clf["all_six_named"]:
        return fail(f"named classes hit={clf['named_classes_hit']}")
    if payload["live_manifest_count"] < 1:
        return fail("no live manifests")
    if payload["live_declaration_count"] < 1:
        return fail("no live declarations")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if L.SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")
    garbage_errs = list(jsonschema.Draft7Validator(schema).iter_errors({}))
    if not garbage_errs:
        return fail("schema accepts empty object")

    stored = None
    for p in doc.get("named_probes") or []:
        if p.get("id") == "probe1":
            stored = p.get("raw_output")
            break
    if not stored:
        return fail("named probe1 raw_output missing")
    stored_doc = json.loads(stored)
    # Compare the classification, not emit timestamps.
    for key in (
        "live_manifest_count",
        "live_declaration_count",
        "syntax_histogram",
        "syntax_histogram_live",
        "classifier_control",
        "live",
        "fixture_classes",
    ):
        if stored_doc.get(key) != payload.get(key):
            return fail(f"artifact drift on {key}")
    census = doc.get("census") or {}
    if census.get("live_declaration_count") != payload["live_declaration_count"]:
        return fail("census live_declaration_count drift")
    if census.get("syntax_histogram") != payload["syntax_histogram"]:
        return fail("census syntax_histogram drift")
    print(
        "SUCCESS:AUD-0025-probe1 constraint-syntax "
        f"live_decls={payload['live_declaration_count']} "
        f"named={clf['named_classes_hit']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
