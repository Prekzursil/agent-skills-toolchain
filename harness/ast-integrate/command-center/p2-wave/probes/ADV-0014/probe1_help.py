#!/usr/bin/env python3
"""Probe 1: source-extracted argv vs live --help, with valid/invalid flag control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import surface as S  # noqa: E402

ART = S.REPO / S.OUTPUT_REL


def main() -> int:
    measured = S.measure_cli()
    print(json.dumps(measured, indent=2, sort_keys=True))
    if not measured.get("control_pass"):
        print("FAILED:ADV-0014-probe1 flag control did not classify valid and invalid")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0014-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    ok, why = S.validate_against_schema(doc)
    print(f"schema_ok={ok} {why}")
    if not ok:
        print("FAILED:ADV-0014-probe1 schema")
        return 1
    if S.SENTINEL not in text:
        print("FAILED:ADV-0014-probe1 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0014-probe1 self-declared {doc.get('state')}")
        return 1
    tests = {t.get("id"): t.get("result") for t in (doc.get("tests") or [])}
    if tests.get("ADV0014-C1-valid-and-invalid-flag") != "PASS":
        print("FAILED:ADV-0014-probe1 control not recorded PASS")
        return 1
    git = next((t for t in (doc.get("targets") or []) if t.get("id") == "cli:git"), None)
    if not git or git.get("verdict") not in S.VERDICTS:
        print("FAILED:ADV-0014-probe1 git target missing")
        return 1
    print("SUCCESS:ADV-0014-probe1 extract+help control passed; live --help classified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
