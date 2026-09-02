#!/usr/bin/env python3
"""Probe 1: fuse sources with distinct licenses; inspect provenance and licence fields."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import lineage as L  # noqa: E402

import jsonschema  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0049-probe1 {msg}")
    return 1


def main() -> int:
    live_m = L.measure()
    payload = L.probe1_payload(live_m)
    print(L.format_probe1(payload))

    if not payload["naive_silent_absorption"]:
        return fail("naive first-licence fuse did not absorb; detector is dead")
    if not payload["preserving_per_source_licence"]:
        return fail("preserving fuse dropped per-source licence; good-state broken")
    if not payload["preserving_per_source_credit"]:
        return fail("preserving fuse dropped credit; good-state broken")
    if payload["compose_per_source_licence"]:
        return fail("live compose unexpectedly kept per-source licence fields")
    if payload["compose_anchor_count"] < 2:
        return fail("live compose dropped both provenance anchors")
    if not payload["incompatible_lattice_pass"]:
        return fail("lattice did not refuse or mark the stricter incompatible term")
    if not payload["incompatible_naive_silent"]:
        return fail("naive incompatible fuse did not silently absorb")

    if not C.ART.is_file() or C.ART.stat().st_size < 200:
        return fail("artifact missing")
    text = C.ART.read_text(encoding="utf-8")
    if C.CATALOG_SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "ADV-0049":
        return fail(f"unit_id={doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in C.NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    schema = C.load_json(C.SCHEMA)
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        return fail(f"schema {errs[0].message}")

    rec = doc.get("probe1_fusion") or {}
    if rec.get("compose_joined") != payload["compose_joined"]:
        return fail("artifact compose_joined drifted from live measure")
    if rec.get("compose_per_source_licence") != payload["compose_per_source_licence"]:
        return fail("artifact compose licence field drifted")
    if rec.get("naive_silent_absorption") is not True:
        return fail("artifact missing naive absorption control")
    compose = (doc.get("fusion_records") or {}).get("compose") or {}
    if "licence_class" not in compose:
        return fail("artifact compose record missing licence_class")
    if compose.get("sources"):
        return fail("live compose unexpectedly grew a sources[] array")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
