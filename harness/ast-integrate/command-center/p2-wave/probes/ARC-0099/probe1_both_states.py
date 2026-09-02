#!/usr/bin/env python3
"""Probe 1: both-states per contract schema, asserted mechanically.

Every schema in ARC-0078..ARC-0087 must accept one instance and semantically
reject one instance. Coverage is covered/defined; uncovered names are listed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0099.json"


def main() -> int:
    rep = C.evaluate()
    print(
        json.dumps(
            {
                "probe": "probe1-both-states",
                "unit_id": "ARC-0099",
                "schemas_defined": rep["schemas_defined"],
                "schemas_covered": rep["schemas_covered"],
                "ratio": rep["ratio"],
                "uncovered": [u["schema_id"] for u in rep["uncovered"]],
                "stand_in": rep["stand_in"],
                "frozen_present": rep["frozen_present"],
            },
            indent=2,
        )
    )
    for row in rep["rows"]:
        print(
            f"{row['schema_id']} accept={row['accept_ok']} "
            f"reject_class={row['reject_class']} covered={row['covered']} "
            f"mutation={row['mutation']} source={row['schema_source']}"
        )
        if not row["accept_ok"]:
            print(f"FAILED:ARC-0099-probe1 {row['schema_id']} accept did not pass")
            print(row.get("accept_reason"))
            return 1
        if not row["reject_semantic_ok"]:
            print(
                f"FAILED:ARC-0099-probe1 {row['schema_id']} reject was not "
                f"the intended semantic violation ({row['intended_keyword']}); "
                f"class={row['reject_class']} keywords={row['reject_keywords']} "
                f"msg={row['reject_message']}"
            )
            return 1
        if not row["covered"]:
            print(f"FAILED:ARC-0099-probe1 {row['schema_id']} not covered")
            return 1
    if not C.both_states_pass(rep):
        print("FAILED:ARC-0099-probe1 both-states coverage incomplete")
        print("uncovered", json.dumps(rep["uncovered"], indent=2))
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ARC-0099-probe1 conformance artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0099-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0099" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0099-probe1 sentinel absent")
        return 1
    cov = doc.get("coverage") or {}
    if int(cov.get("schemas_defined") or 0) != 10:
        print("FAILED:ARC-0099-probe1 artifact schemas_defined != 10")
        return 1
    if int(cov.get("schemas_covered") or 0) != 10:
        print("FAILED:ARC-0099-probe1 artifact schemas_covered != 10")
        return 1
    if cov.get("uncovered"):
        print("FAILED:ARC-0099-probe1 artifact uncovered not empty")
        return 1
    print("SUCCESS:ARC-0099-probe1 both-states per schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
