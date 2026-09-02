#!/usr/bin/env python3
"""IMP-0062 probe 1: generated SBOM validates against official CycloneDX 1.5 schema.

A schema-valid SBOM with the wrong components would still pass this probe;
probe 2 is the independent lockfile set-equality oracle. Both must pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
FIXTURE = PLUGIN / "tests" / "fixtures" / "plugin-closure"
sys.path.insert(0, str(PLUGIN))

from sbom import build_bom, write_bom  # noqa: E402
from validate_cdx import BOM_SCHEMA, validate_bom  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0062.json"
DIST = PLUGIN / "dist" / "sbom.cdx.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0062-probe1 receipt missing")
        return 1
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(receipt)
    if "SUCCESS:IMP-0062" not in text:
        print("FAILED:IMP-0062-probe1 sentinel absent")
        return 1
    if str(receipt.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0062-probe1 self-declared", receipt.get("state"))
        return 1

    bom = build_bom(FIXTURE, timestamp="2026-08-24T18:00:00Z")
    errs = validate_bom(bom)
    if errs:
        print("FAILED:IMP-0062-probe1 schema errors", len(errs))
        for e in errs[:12]:
            print(" ", e)
        return 1

    write_bom(bom, DIST)
    live_errs = validate_bom(json.loads(DIST.read_text(encoding="utf-8")))
    if live_errs:
        print("FAILED:IMP-0062-probe1 dist sbom invalid")
        return 1

    broken = json.loads(json.dumps(bom))
    del broken["specVersion"]
    bad = validate_bom(broken)
    if not bad:
        print("FAILED:IMP-0062-probe1 schema accepted specVersion-removed mutant")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-cyclonedx-schema",
        "unit_id": "IMP-0062",
        "schema": str(BOM_SCHEMA.relative_to(REPO).as_posix()) if BOM_SCHEMA.is_relative_to(REPO) else str(BOM_SCHEMA),
        "spec_version": bom.get("specVersion"),
        "component_count": len(bom.get("components") or []),
        "dist": str(DIST.relative_to(REPO)),
        "mutant_rejected": True,
        "mutant_error_count": len(bad),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"schema_ok=True components={payload['component_count']} "
        f"mutant_rejected={len(bad)} dist={payload['dist']}"
    )
    print("SUCCESS:IMP-0062-probe1 CycloneDX 1.5 schema validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
