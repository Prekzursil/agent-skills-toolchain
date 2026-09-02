#!/usr/bin/env python3
"""Probe 1: every bucket gate is a row; both exit codes; no VALID without them."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    BUCKET_UNITS,
    OUTPUT_REL,
    REPO,
    UNIT_ID,
    catalog_sentinel,
)
from matrix import (  # noqa: E402
    every_bucket_unit_has_row,
    run_bucket,
    valid_requires_both_codes,
)
from schema_util import garbage_rejected, report_body, schema_errors  # noqa: E402

ART = REPO / OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0040-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT_ID:
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    sentinel = catalog_sentinel()
    text = ART.read_text(encoding="utf-8")
    if sentinel not in text:
        return fail("catalog completion_sentinel absent from artifact")
    errs = schema_errors(doc)
    if errs:
        print(errs[0])
        return fail("schema")
    if not garbage_rejected():
        return fail("schema accepted garbage")

    live = run_bucket()
    live_rows = live["gates"]
    body = report_body(doc)
    art_rows = list(body.get("gates") or [])
    if not every_bucket_unit_has_row(art_rows):
        return fail("artifact missing a bucket gate row")
    if not every_bucket_unit_has_row(live_rows):
        return fail("live run missing a bucket gate row")
    if set(BUCKET_UNITS) - {r["id"] for r in art_rows}:
        return fail("artifact rows do not cover BUCKET_UNITS")

    live_fp = {
        r["id"]: (r["broken_exit_code"], r["good_exit_code"], r["verdict"])
        for r in live_rows
    }
    art_fp = {
        r["id"]: (r["broken_exit_code"], r["good_exit_code"], r["verdict"])
        for r in art_rows
        if r.get("id") in BUCKET_UNITS
    }
    if live_fp != art_fp:
        print(json.dumps({"live": live_fp, "artifact": art_fp}, indent=2)[:4000])
        return fail("live matrix fingerprint != artifact")

    for row in art_rows:
        if row.get("broken_exit_code") is None or row.get("good_exit_code") is None:
            return fail(f"{row.get('id')} missing an exit code")
        if not valid_requires_both_codes(row):
            return fail(f"{row.get('id')} VALID without both codes")
        if row.get("verdict") == "NOT-CHECKED" and row.get("verdict") == "VALID":
            return fail("NOT-CHECKED counted VALID")

    fake = {
        "id": "FAKE",
        "verdict": "VALID",
        "broken_exit_code": None,
        "good_exit_code": 0,
    }
    if valid_requires_both_codes(fake):
        return fail("VALID-without-codes helper is broken")

    print(
        json.dumps(
            {
                "probe": "probe1-every-row",
                "unit_id": UNIT_ID,
                "pass": True,
                "bucket": BUCKET_UNITS,
                "rows": len(art_rows),
                "counts": body.get("counts"),
                "all_valid": all(r["verdict"] == "VALID" for r in art_rows),
            },
            sort_keys=True,
        )
    )
    print(
        f"rows={len(art_rows)} bucket={len(BUCKET_UNITS)} "
        f"VALID={body.get('counts', {}).get('VALID')} "
        "no_valid_without_codes=True"
    )
    print("SUCCESS:SYN-0040-probe1 every-bucket-gate-row both-exit-codes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
