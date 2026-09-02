#!/usr/bin/env python3
"""Probe 1: generator sanity — tightened schema must reject a previously-valid instance."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import schemas as S  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0109.json"


def main() -> int:
    live = []
    for uid in S.CONTRACT_IDS:
        schema, source, path = E.load_contract(uid)
        row = E.generator_sanity(schema)
        live.append((uid, source, path, row))
        if not row["original_accepted"]:
            print(f"FAILED:ARC-0109-probe1 generator rejected valid path for {uid} {path}")
            print(json.dumps(row, sort_keys=True))
            return 1
        if not row["tightened_rejected"]:
            print(f"FAILED:ARC-0109-probe1 tightened schema still accepted {uid}")
            return 1
        if not row["live"]:
            print(f"FAILED:ARC-0109-probe1 loop not live for {uid} reasons={row['tightened_reasons']}")
            return 1
    if not ART.is_file():
        print("FAILED:ARC-0109-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0109-probe1 self-declared {doc.get('state')}")
        return 1
    gs = doc.get("generator_sanity") or {}
    if gs.get("live") is not True:
        print("FAILED:ARC-0109-probe1 artifact generator_sanity.live is not true")
        return 1
    if gs.get("original_accepted") is not True or gs.get("tightened_rejected") is not True:
        print("FAILED:ARC-0109-probe1 artifact sanity flags incomplete")
        return 1
    if "SUCCESS:ARC-0109" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0109-probe1 sentinel absent")
        return 1
    n = len(live)
    print(
        json.dumps(
            {
                "schemas": n,
                "all_original_accepted": True,
                "all_tightened_rejected": True,
                "loop_live": True,
                "artifact_live": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:ARC-0109-probe1 generator-sanity live on {n} schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
