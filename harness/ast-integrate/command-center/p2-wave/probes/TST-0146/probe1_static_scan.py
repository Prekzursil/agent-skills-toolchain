#!/usr/bin/env python3
"""Probe 1: static scan of write call sites (independent of crash injection)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scan import scan_emit_receipt, scan_writers  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0146-probe1 {msg}")
    return 1


def main() -> int:
    writers = scan_writers()
    emit = scan_emit_receipt()
    if not writers["production_all_atomic"]:
        return fail(f"production writers not atomic: {writers['production_bad']}")
    if not writers["control_detected"]:
        return fail("detector control missed non_atomic_publish / child_non_atomic")
    if not emit["uses_atomic_publish"]:
        return fail("emit_receipt.py does not call atomic_publish")
    if emit["inplace_catalog_write"]:
        return fail("emit_receipt.py writes the catalog artifact in place")
    payload = {
        "pass": True,
        "probe": "probe1-static-scan",
        "unit_id": "TST-0146",
        "production_all_atomic": True,
        "control_detected": True,
        "emit_uses_atomic_publish": True,
        "production": writers["production"],
        "control": writers["control"],
        "emit": emit,
        "write_sites_enumerated": [
            {
                "file": r["file"],
                "function": r["name"],
                "class": r["class"],
                "has_tmp": r["has_tmp"],
                "has_replace": r["has_replace"],
            }
            for r in writers["functions"]
            if r["name"]
            in {
                "atomic_publish",
                "child_atomic",
                "non_atomic_publish",
                "child_non_atomic",
            }
        ],
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        "production_atomic=True control_detected=True "
        "emit_atomic_publish=True"
    )
    print("SUCCESS:TST-0146-probe1 static scan of write sites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
