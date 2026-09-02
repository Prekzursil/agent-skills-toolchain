#!/usr/bin/env python3
"""Validate the ADV-0085 artifact against its schema and catalog rules."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402

ALLOWED = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0085-validate {msg}")
    return 1


def main() -> int:
    if not C.ART.is_file() or C.ART.stat().st_size < 200:
        return fail("artifact missing")
    text = C.ART.read_text(encoding="utf-8")
    if C.CATALOG_SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    schema = json.loads((REPO / C.SCHEMA_REL).read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        return fail(f"schema {errors[0].message}")
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            return fail("schema accepted garbage")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    seen = []
    for t in doc.get("targets") or []:
        tid = t.get("target_id") or t.get("target_id")
        verd = t.get("verdict") or t.get("verdict")
        if tid in seen:
            return fail(f"duplicate target {tid}")
        seen.append(tid)
        if verd not in ALLOWED:
            return fail(f"illegal verdict {verd}")
    probes = doc.get("named_probes") or doc.get("named_probes") or []
    if len(probes) < 2:
        return fail("named probes < 2")
    for p in probes:
        if not str(p.get("raw_output") or "").strip():
            return fail(f"empty raw_output {p.get('id')}")
    ncs = doc.get("negative_controls") or []
    if not ncs:
        return fail("negative controls missing")
    print(
        f"targets={len(seen)} probes={len(probes)} controls={len(ncs)} "
        f"state={doc.get('state')} overall={doc.get('overall_verdict') or doc.get('overall_verdict')}"
    )
    print("SUCCESS:ADV-0085-validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
