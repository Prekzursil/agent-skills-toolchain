#!/usr/bin/env python3
"""Probe 1: keyword search over event-ledger files.

Recomputes substring hits on ledger events. Does not score memory notes and
does not apply pin contradictions — that is probe 2. Disagreement with the
artifact's recorded ledger-control hit set is a failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import stores as S  # noqa: E402

ART = REPO / "command-center/audit/AUD-0065-ledger-memory-state-inventory.json"
SENTINEL = "SUCCESS:AUD-0065"
COMPLETION = (
    "SUCCESS:AUD-0065 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0065-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        return fail("sentinel absent")
    if COMPLETION not in blob:
        return fail("completion_sentinel absent")
    if doc.get("unit_id") != "AUD-0065":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    pack = S.load_stores()
    live = E.keyword_hits(pack["ledger_all"], E.LEDGER_CONTROL)
    mem_leak = E.keyword_hits(pack["ledger_all"], E.MEMORY_ONLY)
    recorded = [
        h
        for h in (doc.get("ledger_control_hits") or [])
        if isinstance(h, dict)
    ]
    live_ids = {h["id"] for h in live}
    rec_ids = {h["id"] for h in recorded}
    headline = doc.get("headline") or {}
    print(
        json.dumps(
            {
                "probe": "probe1-ledger-keyword",
                "unit_id": "AUD-0065",
                "live_control_hits": len(live),
                "recorded_control_hits": len(recorded),
                "memory_nonce_in_ledger": len(mem_leak),
                "catalog_ledger_exists": pack["catalog_ledger_exists"],
                "live_ledger_events": len(pack["live_ledger"]),
                "equal": live_ids == rec_ids,
            },
            sort_keys=True,
        )
    )
    if not live:
        return fail("planted ledger control token produced zero hits; keyword detector is inert")
    if live_ids != rec_ids:
        return fail(f"control hit set mismatch live={sorted(live_ids)} rec={sorted(rec_ids)}")
    if int(headline.get("ledger_control_hits") or -1) != len(live):
        return fail("headline ledger_control_hits disagrees with live")
    if int(headline.get("live_ledger_events", -1)) != len(pack["live_ledger"]):
        return fail("headline live_ledger_events disagrees with live")
    if bool(headline.get("catalog_ledger_exists")) != bool(pack["catalog_ledger_exists"]):
        return fail("headline catalog_ledger_exists disagrees with live")
    if mem_leak:
        return fail("memory-only nonce leaked into ledger keyword hits")
    print("probe1_did_not_search_memory_notes=True")
    print("SUCCESS:AUD-0065-probe1 ledger keyword control hits match live extraction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
