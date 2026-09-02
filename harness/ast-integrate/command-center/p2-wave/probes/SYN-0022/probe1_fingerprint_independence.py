#!/usr/bin/env python3
"""Probe 1: every delivered record is an independent CNF-0006 pair; live re-measure matches."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cnf0006_fingerprint import (  # noqa: E402
    INDEPENDENT,
    fingerprint_hex,
    pair_status,
)
from constants import (  # noqa: E402
    OUTPUT_REL,
    UNIT_ID,
    catalog_sentinel,
)
from facts import (  # noqa: E402
    build_records,
    fingerprint_spec_of,
    records_of,
)
from schema_util import schema_errors  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0022-probe1 {msg}")
    return 1


def main() -> int:
    art_path = REPO / OUTPUT_REL
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        return fail("artifact missing")
    text = art_path.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != UNIT_ID:
        return fail(f"unit_id {doc.get('unit_id')}")
    sentinel = catalog_sentinel()
    if sentinel not in text:
        return fail("sentinel-absent")
    errors = schema_errors(doc)
    if errors:
        return fail(f"schema {errors[0]}")

    records = records_of(doc)
    if len(records) < 4:
        return fail(f"records {len(records)}")
    live = {row["fact_id"]: row for row in build_records()}
    for row in records:
        fid = row.get("fact_id")
        src = row.get("source_probe")
        ver = row.get("verifier_probe")
        status = pair_status(src, ver)
        if status != INDEPENDENT:
            return fail(f"{fid} pair_status={status}")
        if fingerprint_hex(src) == fingerprint_hex(ver):
            return fail(f"{fid} verifier duplicates source fingerprint")
        if row.get("pair_status") != INDEPENDENT:
            return fail(f"{fid} recorded pair_status {row.get('pair_status')}")
        if row.get("verdict") == "CONFIRMED" and status != INDEPENDENT:
            return fail(f"{fid} CONFIRMED without independence")
        if fid not in live:
            return fail(f"{fid} missing from live rebuild")
        rebuilt = live[fid]
        if rebuilt["verdict"] != row.get("verdict"):
            return fail(
                f"{fid} live verdict {rebuilt['verdict']} != {row.get('verdict')}"
            )
        # SUCCESS-count census moves when sibling units land artifacts.
        # Independence and verdict must still match; the integer may not.
        if fid != "F-DELIVERED-COUNT-4":
            if rebuilt["verifier_output"] != row.get("verifier_output"):
                return fail(f"{fid} live verifier_output drift")
        if rebuilt["source_fingerprint"] != row.get("source_fingerprint"):
            return fail(f"{fid} source fingerprint drift")
        if rebuilt["verifier_fingerprint"] != row.get("verifier_fingerprint"):
            return fail(f"{fid} verifier fingerprint drift")
        print(
            f"{fid} independent source={row['source_fingerprint'][:12]} "
            f"verifier={row['verifier_fingerprint'][:12]} verdict={row.get('verdict')}"
        )
    axes = (fingerprint_spec_of(doc) or {}).get("axes") or []
    if list(axes) != ["tool", "shell", "data_field", "measurement_kind"]:
        return fail(f"fingerprint axes {axes}")
    print(f"records={len(records)} all independent live-match")
    print("SUCCESS:SYN-0022-probe1 source-and-verifier fingerprints differ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
