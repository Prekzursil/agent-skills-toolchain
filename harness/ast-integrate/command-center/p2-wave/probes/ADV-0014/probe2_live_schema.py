#!/usr/bin/env python3
"""Probe 2: resolve source MCP names against live tool schema (not docs)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import surface as S  # noqa: E402

ART = S.REPO / S.OUTPUT_REL


def main() -> int:
    measured = S.measure_mcp()
    print(json.dumps(measured, indent=2, sort_keys=True))
    if not measured.get("control_pass"):
        print("FAILED:ADV-0014-probe2 hyphen/underscore or planted-absent control")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0014-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    ok, why = S.validate_against_schema(doc)
    print(f"schema_ok={ok} {why}")
    if not ok:
        print("FAILED:ADV-0014-probe2 schema")
        return 1
    if S.SENTINEL not in text:
        print("FAILED:ADV-0014-probe2 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0014-probe2 self-declared {doc.get('state')}")
        return 1
    tests = {t.get("id"): t.get("result") for t in (doc.get("tests") or [])}
    if tests.get("ADV0014-C2-hyphen-vs-underscore") != "PASS":
        print("FAILED:ADV-0014-probe2 hyphen control not recorded PASS")
        return 1
    if tests.get("ADV0014-C3-planted-absent-mcp") != "PASS":
        print("FAILED:ADV-0014-probe2 planted-absent control not recorded PASS")
        return 1
    mcp_targets = [t for t in (doc.get("targets") or []) if str(t.get("id") or "").startswith("mcp:")]
    if not mcp_targets:
        print("FAILED:ADV-0014-probe2 no mcp targets")
        return 1
    print("SUCCESS:ADV-0014-probe2 live schema resolve; hyphen identity distinct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
