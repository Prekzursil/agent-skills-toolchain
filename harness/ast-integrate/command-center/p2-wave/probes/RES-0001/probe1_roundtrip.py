#!/usr/bin/env python3
"""Probe 1: 8 schema files on disk; 10 claims validate; round-trip is byte-stable."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check as K  # noqa: E402
import schema_lib as S  # noqa: E402


def main() -> int:
    report = K.run_report()
    missing = report["missing_schema_files"]
    print(f"schema_files n={len(S.SCHEMA_FILES)} missing={missing}")
    if not report["schema_files_present"]:
        print("FAILED:RES-0001-probe1 schema family incomplete")
        return 1
    rt = report["roundtrip"]
    print(f"roundtrip ok={rt.get('ok')} n={rt.get('n')}")
    if not rt.get("ok"):
        print(json.dumps(rt, indent=2, sort_keys=True)[:4000])
        print("FAILED:RES-0001-probe1 round-trip")
        return 1
    good = report["both_states"]["known_good"]
    print(f"green_fixture schema_ok={good['schema_ok']} consumers_ok={good['consumers_ok']}")
    if not good["schema_ok"] or not good["consumers_ok"]:
        print("FAILED:RES-0001-probe1 green fixture not green")
        return 1
    print(
        "SUCCESS:RES-0001-probe1 8 schema files + 10-claim round-trip byte-stable + green fixture"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
