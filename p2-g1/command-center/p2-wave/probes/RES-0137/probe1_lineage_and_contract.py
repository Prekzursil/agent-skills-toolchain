#!/usr/bin/env python3
"""Probe 1: live artifact lineage, two-signal claims, mixed transfer set."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402


def main() -> int:
    if not C.ART.is_file():
        print("FAILED:RES-0137-probe1 artifact missing")
        return 1
    doc = C.load_json(C.ART)
    result = C.transfer_scan(doc)
    print(json.dumps({k: result[k] for k in sorted(result)}, default=str))
    if not result["pass"]:
        print("FAILED:RES-0137-probe1 contract")
        return 1
    text = C.ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        print("FAILED:RES-0137-probe1 sentinel")
        return 1
    if str(doc.get("state") or "").upper() in C.NOT_DELIVERING:
        print(f"FAILED:RES-0137-probe1 self-declared {doc.get('state')}")
        return 1
    print(
        f"communities=5 mechanisms={len(doc.get('mechanisms') or [])} "
        f"transfer={result['n_transfer']} not_transfer={result['n_not_transfer']} "
        f"claims={result['n_claims']}"
    )
    print("SUCCESS:RES-0137-probe1 lineage and transfer contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
