#!/usr/bin/env python3
"""Probe 1: a RUN cell is a version-stamped evidence anchor, or it is NEVER-RUN."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coverage_gate as G  # noqa: E402
import test_coverage_gate as T  # noqa: E402
import validate_receipt_schema as V  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0006.json"


def main() -> int:
    T.test_run_requires_version()
    T.test_classify_run_needs_both_signals()
    print("control version-less RUN -> NEVER-RUN")

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:BLD-0006-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:BLD-0006" not in text:
        print("FAILED:BLD-0006-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:BLD-0006-probe1 self-declared {doc.get('state')}")
        return 1
    errs = V.validate_doc(doc)
    if errs:
        print("FAILED:BLD-0006-probe1 schema")
        print("\n".join(errs[:8]))
        return 1
    if not V.garbage_rejected():
        print("FAILED:BLD-0006-probe1 schema vacuous")
        return 1

    cells = doc.get("cells") or []
    if len(cells) < 3:
        print(f"FAILED:BLD-0006-probe1 too few cells {len(cells)}")
        return 1
    run = [c for c in cells if c.get("status") == "RUN"]
    for cell in run:
        ver = (cell.get("client_version") or "") or (
            (cell.get("evidence") or {}).get("client_version") or ""
        )
        if not str(ver).strip():
            print(f"FAILED:BLD-0006-probe1 RUN without version {cell.get('id')}")
            return 1
        gate_errs = G.validate_cell(cell)
        if gate_errs:
            print(
                f"FAILED:BLD-0006-probe1 RUN failed gate {cell.get('id')} {gate_errs}"
            )
            return 1
    print(f"cells={len(cells)} run={len(run)} version_anchor_ok=True")
    print("SUCCESS:BLD-0006-probe1 version-stamped evidence anchor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
