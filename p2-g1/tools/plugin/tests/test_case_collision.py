#!/usr/bin/env python3
"""IMP-0009: case-distinct JSON keys and exact duplicate keys are findings."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
sys.path.insert(0, str(PLUGIN))

import case_collision as cc  # noqa: E402

FIX = HERE / "fixtures"


def main() -> int:
    clean = cc.lint_file(FIX / "clean-manifest.json")
    planted = cc.lint_file(FIX / "name-collision.json")
    dup = cc.lint_file(FIX / "duplicate-keys.json")
    nested = cc.lint_file(FIX / "nested-collision.json")
    siblings = cc.lint_file(FIX / "non-colliding-siblings.json")
    if not clean["parse_ok"] or clean["findings"]:
        print("FAILED:test_case_collision clean")
        print(json.dumps(clean, indent=2))
        return 1
    case_hits = [f for f in planted["findings"] if f["kind"] == cc.KIND_CASE]
    if not case_hits or set(case_hits[0]["keys"]) != {"Name", "name"}:
        print("FAILED:test_case_collision planted Name/name")
        print(json.dumps(planted, indent=2))
        return 1
    dup_hits = [f for f in dup["findings"] if f["kind"] == cc.KIND_DUP]
    if not dup_hits:
        print("FAILED:test_case_collision duplicate name")
        return 1
    nest_hits = [f for f in nested["findings"] if f["kind"] == cc.KIND_CASE]
    if not nest_hits:
        print("FAILED:test_case_collision nested Title/title")
        return 1
    if siblings["findings"]:
        print("FAILED:test_case_collision siblings collided")
        return 1
    print("SUCCESS:test_case_collision")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
