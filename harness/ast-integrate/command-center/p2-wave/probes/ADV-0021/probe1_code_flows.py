#!/usr/bin/env python3
"""Probe 1: enumerate install-path trust boundaries and STRIDE cells from code."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import UNIT, probe1_payload  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    payload = probe1_payload()
    compact = {
        "probe": "probe1-code-flows",
        "unit_id": UNIT,
        "pass": payload.get("pass"),
        "reason": payload.get("reason"),
        "method": payload.get("method"),
        "files": payload.get("files"),
        "missing_files": payload.get("missing_files"),
        "signature_called_from_marketplace_install": payload.get(
            "signature_called_from_marketplace_install"
        ),
        "journal_called_from_install": payload.get("journal_called_from_install"),
        "windows_registry_hits": payload.get("windows_registry_hits"),
        "boundary_count": payload.get("boundary_count"),
        "cell_count": payload.get("cell_count"),
        "mitigated": payload.get("mitigated"),
        "partial": payload.get("partial"),
        "unmitigated": payload.get("unmitigated"),
        "boundaries": [
            {
                "id": b.get("id"),
                "from": b.get("from"),
                "to": b.get("to"),
                "operation": b.get("operation"),
                "code_anchor": b.get("code_anchor"),
            }
            for b in payload.get("boundaries") or []
        ],
        "cells": [
            {
                "id": c.get("id"),
                "status": c.get("status"),
                "control_anchor": c.get("control_anchor"),
            }
            for c in payload.get("stride_cells") or []
        ],
    }
    print(json.dumps(compact, sort_keys=True, default=str))
    if not payload.get("pass"):
        return fail(str(payload.get("reason") or "enumeration failed"))
    if int(payload.get("boundary_count") or 0) < 5:
        return fail("too few boundaries")
    if int(payload.get("cell_count") or 0) < 30:
        return fail("too few STRIDE cells")
    if int(payload.get("mitigated") or 0) < 1 or int(payload.get("unmitigated") or 0) < 1:
        return fail("model is not two-sided")
    print(
        f"boundaries={payload['boundary_count']} cells={payload['cell_count']} "
        f"mitigated={payload['mitigated']} unmitigated={payload['unmitigated']}"
    )
    print("SUCCESS:ADV-0021-probe1 code-derived STRIDE enumeration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
