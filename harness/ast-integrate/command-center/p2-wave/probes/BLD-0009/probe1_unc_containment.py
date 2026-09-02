#!/usr/bin/env python3
"""Probe 1: UNC reject, link containment, fixture control, scratch isolation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = H.REPO / "command-center/receipts/BLD-0009.json"


def main() -> int:
    matrix = H.run_matrix()
    by_id = {c["id"]: c for c in matrix["cells"]}
    required = ("unc_share", "symlink_escape", "hardlink", "fixture_control")
    for cell_id in required:
        cell = by_id.get(cell_id)
        print(f"{cell_id} verdict={cell and cell['verdict']} error={cell and cell.get('named_error')}")
        if not cell or cell["verdict"] != "EXERCISED":
            print(f"FAILED:BLD-0009-probe1 {cell_id} not EXERCISED")
            return 1
    if not matrix["outside_sentinel_intact"]:
        print("FAILED:BLD-0009-probe1 outside sentinel mutated")
        return 1
    if not H.fixture_negative_fails():
        print("FAILED:BLD-0009-probe1 negative fixture control did not fail")
        return 1
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:BLD-0009-probe1 self-declared {doc.get('state')}")
            return 1
        if "SUCCESS:BLD-0009" not in ART.read_text(encoding="utf-8"):
            print("FAILED:BLD-0009-probe1 sentinel absent")
            return 1
    print("SUCCESS:BLD-0009-probe1 UNC containment fixture-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
