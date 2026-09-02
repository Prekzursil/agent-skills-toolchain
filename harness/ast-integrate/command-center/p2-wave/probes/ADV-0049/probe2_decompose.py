#!/usr/bin/env python3
"""Probe 2: decompose fused records; metadata-only lineage is unverifiable.

Re-derives round-trip from fusion_records in the artifact (and from a live
re-run of the same engines). Does not read targets[].verdict.
"""
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
    print(f"FAILED:ADV-0049-probe2 {msg}")
    return 1


def main() -> int:
    live_m = L.measure()
    payload = L.probe2_payload(live_m)
    print(L.format_probe2(payload))

    if not payload["preserving_roundtrip"]:
        return fail("preserving decompose is not an inverse; oracle broken")
    if payload["compose_roundtrip"]:
        return fail("compose members-only record reconstructed full sources")
    if payload["naive_roundtrip"]:
        return fail("naive fuse reconstructed sources it never stored")
    if not payload["meta_only_unverifiable"]:
        return fail("metadata-only fusion was treated as decomposable")

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

    records = doc.get("fusion_records") or {}
    fix = L.load_fixture()
    left, right = L.pair(fix, "compatible_pair")
    for key, expect_ok in (
        ("preserving", True),
        ("compose", False),
        ("naive", False),
        ("meta_only", False),
    ):
        fusion = records.get(key)
        if not isinstance(fusion, dict):
            return fail(f"fusion_records.{key} missing")
        got = L.roundtrip_ok(fusion, left, right)
        if bool(got["ok"]) != expect_ok:
            return fail(
                f"re-derived {key} roundtrip ok={got['ok']} expected {expect_ok} "
                f"method={got['method']} mismatches={got['mismatches']}"
            )

    rec = doc.get("probe2_decompose") or {}
    if rec.get("preserving_roundtrip") is not True:
        return fail("artifact preserving_roundtrip drifted")
    if rec.get("compose_roundtrip") is not False:
        return fail("artifact compose_roundtrip drifted")
    if rec.get("meta_only_unverifiable") is not True:
        return fail("artifact meta_only_unverifiable drifted")
    # Do not read doc['targets'] — reviewer re-derives from fusion_records.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
