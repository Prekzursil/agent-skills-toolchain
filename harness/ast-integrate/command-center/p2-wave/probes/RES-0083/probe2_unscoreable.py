#!/usr/bin/env python3
"""Probe 2: unscoreable output type identified; E3 cannot promote a mechanism."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from check_artifact import (  # noqa: E402
    ART,
    check_e3_cannot_promote,
    check_live,
    check_unscoreable,
    expect_fail,
    load_doc,
    mutant_drop_unscoreable,
    mutant_e3_promoted,
)


def recommended_have_resolution(doc: dict) -> None:
    for row in doc.get("rule_table") or []:
        if str(row.get("recommendation") or "") != "RECOMMENDED":
            continue
        src = str(row.get("resolution_source") or "").strip()
        if not src:
            raise AssertionError(f"recommended {row.get('id')} has no resolution_source")
        if row.get("effect_size", {}).get("value") is None:
            raise AssertionError(f"recommended {row.get('id')} missing effect_size")
        if row.get("baseline", {}).get("value") is None:
            raise AssertionError(f"recommended {row.get('id')} missing baseline")


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0083-probe2 artifact absent")
        return 1
    doc = load_doc()
    summary = check_live(doc)
    u = check_unscoreable(doc)
    check_e3_cannot_promote(doc)
    recommended_have_resolution(doc)
    expect_fail(check_unscoreable, mutant_drop_unscoreable(doc), "drop-unscoreable mutant")
    expect_fail(check_e3_cannot_promote, mutant_e3_promoted(doc), "E3-promoted mutant")

    e3_rows = [
        r.get("id")
        for r in doc["rule_table"]
        if str(r.get("evidence_tier") or "") == "E3"
    ]
    recs = [
        r.get("id")
        for r in doc["rule_table"]
        if str(r.get("recommendation") or "") == "RECOMMENDED"
    ]
    out = {
        "probe": "probe2-unscoreable-e3-control",
        "unit_id": "RES-0083",
        "pass": True,
        "unscoreable_id": u.get("id"),
        "unscoreable_is_control": True,
        "e3_rows": e3_rows,
        "recommended_ids": recs,
        "drop_unscoreable_mutant_red": True,
        "e3_promoted_mutant_red": True,
        "live_ok": summary.get("ok"),
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:RES-0083-probe2 unscoreable type identified and E3 cannot promote")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAILED:RES-0083-probe2 {exc}")
        raise SystemExit(1)
