#!/usr/bin/env python3
"""Probe 1: rule table has a named resolution source per row; Brier arithmetic holds."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from check_artifact import (  # noqa: E402
    ART,
    SENTINEL,
    check_mellers_arithmetic,
    check_rule_table,
    check_sentinel_and_state,
    expect_fail,
    load_doc,
    mutant_missing_resolution,
)

from scoring import brier_binary  # noqa: E402


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0083-probe1 artifact absent")
        return 1
    doc = load_doc()
    check_sentinel_and_state(doc)
    ids = check_rule_table(doc)
    check_mellers_arithmetic()
    expect_fail(check_rule_table, mutant_missing_resolution(doc), "missing-resolution mutant")

    sources = [str(r.get("resolution_source") or "") for r in doc["rule_table"]]
    if any(not s.strip() for s in sources):
        print("FAILED:RES-0083-probe1 unnamed resolution")
        return 1

    hit = brier_binary(0.9, 1)
    miss = brier_binary(0.9, 0)
    out = {
        "probe": "probe1-rule-table",
        "unit_id": "RES-0083",
        "pass": True,
        "sentinel_present": SENTINEL in json.dumps(doc),
        "n_rules": len(ids),
        "rule_ids": ids,
        "resolution_sources_named": len(sources),
        "mellers_hit_brier": hit,
        "mellers_miss_brier": miss,
        "missing_resolution_mutant_red": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:RES-0083-probe1 rule table named resolution sources and Brier control")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAILED:RES-0083-probe1 {exc}")
        raise SystemExit(1)
