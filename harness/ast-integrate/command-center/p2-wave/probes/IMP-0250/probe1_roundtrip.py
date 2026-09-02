#!/usr/bin/env python3
"""Probe 1: planted in-field control does not shift columns (round-trip equality)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ast_order
import blueprints
import extract_normalize as en


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0250-probe1 {msg}")
    return 1


def main() -> int:
    planted = en.planted_fixture()
    if b"\x1f" not in planted:
        return fail("fixture lost the planted US byte")
    rows = en.parse_table(planted)
    expected = en.expected_normalized()
    if rows != expected:
        return fail(f"normalized rows != expected: {rows!r}")
    widths = [len(r) for r in rows]
    if widths != [3, 3, 3]:
        return fail(f"column shift under fixed parser widths={widths}")
    if rows[1][1] != b"widgetdeluxe":
        return fail(f"title not sanitized in-place: {rows[1][1]!r}")

    emitted = en.emit_normalized(rows)
    if b"\x1f" in emitted:
        return fail("emit leaked US")
    round_trip = en.parse_table(emitted)
    if round_trip != rows:
        return fail("round-trip inequality after emit+parse")

    benign = en.parse_table(en.benign_fixture())
    if benign != expected:
        return fail("benign fixture diverged from normalized planted")

    order = ast_order.check_parse_order(HERE / "extract_normalize.py")
    if not order.get("ok"):
        return fail(f"AST sanitize-before-split: {order}")

    regs = blueprints.register_all()
    if not all(r.get("registered") for r in regs) or len(regs) != 4:
        return fail(f"blueprint registration {regs}")
    omissions = blueprints.contract_omission_controls()
    if not all(v["distinct"] and v["all_rejected"] for v in omissions.values()):
        return fail(f"omission matrix {omissions}")

    smokes = {
        "extract": en.smoke(),
        "quality": __import__("data_quality").smoke(),
        "docs": __import__("dataset_docs").smoke(),
        "kb": __import__("knowledge_base").smoke(),
    }
    if not all(s.get("ok") for s in smokes.values()):
        return fail(f"smoke {smokes}")

    print(
        json.dumps(
            {
                "widths": widths,
                "round_trip": True,
                "planted_us": True,
                "ast_order": order,
                "registered": [r["id"] for r in regs],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0250-probe1 round-trip and sanitize-before-split")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
