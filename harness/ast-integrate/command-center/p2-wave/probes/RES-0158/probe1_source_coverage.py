#!/usr/bin/env python3
"""Probe 1: every technique has two rails, live quotes, ACH critique present."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import REQUIRED_TECHNIQUES, evaluate_table, techniques  # noqa: E402
from lib import (  # noqa: E402
    ARTIFACT,
    MIN_BYTES,
    NOT_DELIVERING,
    SENTINEL,
    UID,
    live_capture_row,
    quote_in_capture,
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0158-probe1 {msg}")
    return 1


def main() -> int:
    rows = techniques()
    ev = evaluate_table(rows)
    print(
        f"live n={ev['n']} direct={ev['n_directly_implementable']} "
        f"not_proto={ev['n_not_a_protocol']} ach_critique={ev['ach_critique_present']} "
        f"icd_not={ev['icd203_not_protocol']} quotes_ok={ev['quotes_ok']}"
    )
    if not ev["ok"]:
        return fail(f"live-table {ev}")

    if not ARTIFACT.is_file():
        return fail("artifact-absent")
    raw = ARTIFACT.read_bytes().replace(b"\r\n", b"\n")
    if len(raw) < MIN_BYTES:
        return fail("artifact-too-small")
    text = raw.decode("utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        return fail("not-object")
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("unit_id") != UID:
        return fail("unit-id")

    art_rows = doc.get("techniques") or []
    if len(art_rows) != len(rows):
        return fail(f"table-len artifact={len(art_rows)} live={len(rows)}")
    by_id = {r.get("id"): r for r in art_rows if isinstance(r, dict)}
    for live in rows:
        rec = by_id.get(live["id"])
        if rec is None:
            return fail(f"missing-row {live['id']}")
        if rec.get("transfer_verdict") != live["transfer_verdict"]:
            return fail(f"verdict-drift {live['id']}")
        if rec.get("protocol_id") != live["protocol_id"]:
            return fail(f"protocol-drift {live['id']}")
        fm = rec.get("failure_mode") or {}
        if live["id"] == "ach":
            if fm.get("entrench_bad_hypothesis_set") is not True:
                return fail("ach-critique-absent")
            if fm.get("published_critique") is not True:
                return fail("ach-published-critique-absent")
        lineage = rec.get("source_lineage") or []
        if len(lineage) < 2:
            return fail(f"one-rail {live['id']}")
        rails = {str(x.get("rail") or "") for x in lineage}
        if len(rails) < 2:
            return fail(f"rails-not-independent {live['id']} {rails}")
        for lin in lineage:
            cid = str(lin.get("id") or "")
            quote = str(lin.get("quote") or "")
            if not cid or not quote:
                return fail(f"lineage-empty {live['id']}")
            live_cap = live_capture_row(cid)
            if lin.get("sha256_of_fetched_bytes") != live_cap["sha256_of_fetched_bytes"]:
                return fail(f"sha-drift {cid}")
            if not quote_in_capture(cid, quote):
                return fail(f"quote-absent {live['id']} {cid}")
            for key in ("resolved_url", "fetch_timestamp"):
                if not lin.get(key):
                    return fail(f"lineage-missing {live['id']} {key}")

    claims = doc.get("claims") or []
    if len(claims) != len(REQUIRED_TECHNIQUES):
        return fail(f"claims-len {len(claims)}")
    for c in claims:
        if c.get("sherman_kent_band") not in {
            "almost-certain",
            "likely",
            "roughly-even",
            "unlikely",
            "remote",
        }:
            return fail(f"band {c.get('claim_id')}")
        if len(c.get("signals") or []) < 2:
            return fail(f"signals {c.get('claim_id')}")
        if len(c.get("lineage") or []) < 1:
            return fail(f"claim-lineage {c.get('claim_id')}")

    print("SUCCESS:RES-0158-probe1 source-coverage two-rails ACH-critique")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
