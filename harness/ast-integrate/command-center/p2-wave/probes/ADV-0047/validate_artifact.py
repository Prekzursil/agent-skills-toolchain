#!/usr/bin/env python3
"""Validate ADV-0047 artifact against catalog schema and unit contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    COMPLETION_SENTINEL,
    LEGAL_VERDICTS,
    NOT_DELIVERING,
    OUTPUT_REL,
    SCHEMA_REL,
    UNIT_ID,
)


def load_artifact() -> tuple[dict, str]:
    path = REPO / OUTPUT_REL
    if not path.is_file() or path.stat().st_size <= 0:
        raise SystemExit("FAILED:ADV-0047 artifact missing")
    text = path.read_text(encoding="utf-8")
    doc = json.loads(text)
    return doc, text


def validate(doc: dict, text: str) -> list[str]:
    errors: list[str] = []
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    errs = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        errors.append("schema:" + errs[0].message)
    if doc.get("unit_id") != UNIT_ID:
        errors.append("unit_id")
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        errors.append("self-declared:" + str(doc.get("state")))
    if COMPLETION_SENTINEL not in text:
        errors.append("sentinel-absent")
    targets = doc.get("targets") or []
    if len(targets) < 1:
        errors.append("targets-empty")
    seen: set[str] = set()
    for t in targets:
        if not isinstance(t, dict):
            errors.append("target-not-object")
            continue
        tid = str(t.get("id") or "")
        verd = str(t.get("verdict") or "")
        if tid in seen:
            errors.append("duplicate-target:" + tid)
        seen.add(tid)
        if verd not in LEGAL_VERDICTS:
            errors.append("illegal-verdict:" + tid + ":" + verd)
    probes = doc.get("probes") or []
    if len(probes) < 2:
        errors.append("probes-missing")
    ids = {p.get("id") for p in probes if isinstance(p, dict)}
    if "probe1-snapshot-diff" not in ids or "probe2-behavioral" not in ids:
        errors.append("named-probes-missing")
    for p in probes:
        if isinstance(p, dict) and not str(p.get("raw_output") or "").strip():
            errors.append("probe-raw-empty:" + str(p.get("id")))
    controls = doc.get("controls") or []
    if not controls:
        errors.append("controls-missing")
    tests = doc.get("tests") or []
    if len(tests) < 2:
        errors.append("tests-missing")
    if not isinstance(doc.get("intentional_retention"), list):
        errors.append("intentional_retention-missing")
    if not isinstance(doc.get("unintentional_residue"), list):
        errors.append("unintentional_residue-missing")
    return errors


def main() -> int:
    doc, text = load_artifact()
    errors = validate(doc, text)
    if errors:
        print("FAILED:ADV-0047-validate " + ";".join(errors[:8]))
        return 1
    print(
        json.dumps(
            {
                "probe": "validate-artifact",
                "unit_id": UNIT_ID,
                "state": doc.get("state"),
                "n_targets": len(doc.get("targets") or []),
                "n_probes": len(doc.get("probes") or []),
                "n_controls": len(doc.get("controls") or []),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ADV-0047-validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
