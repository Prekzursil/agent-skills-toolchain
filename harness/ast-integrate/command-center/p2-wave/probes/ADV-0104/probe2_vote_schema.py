#!/usr/bin/env python3
"""Probe 2: independent vote-schema evidence-anchor requiredness review."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

ART = H.REPO / H.OUTPUT_REL
SCHEMA = H.REPO / H.SCHEMA_REL


def main() -> int:
    payload = H.probe2_payload()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload.get("evidence_anchor_required_on_vote") is True:
        print("FAILED:ADV-0104-probe2 expected evidence anchor not required on vote")
        return 1
    if not payload.get("defect_exists_for_every_council"):
        print("FAILED:ADV-0104-probe2 schema requiredness did not show a universal defect")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0104-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:ADV-0104-probe2 self-declared", doc.get("state"))
        return 1
    if H.CATALOG_PROBE2 not in text:
        print("FAILED:ADV-0104-probe2 catalog probe-2 text absent")
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print("FAILED:ADV-0104-probe2 schema", errs[0].message)
        return 1
    audit = doc.get("schema_audit") or {}
    if audit.get("defect_exists_for_every_council") is not True:
        print("FAILED:ADV-0104-probe2 artifact schema audit mismatch")
        return 1
    if doc.get("reviewer", {}).get("independent") is not True:
        print("FAILED:ADV-0104-probe2 reviewer not independent")
        return 1
    print(
        "SUCCESS:ADV-0104-probe2 evidence anchor is not required on a vote; "
        "defect exists for every council"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
