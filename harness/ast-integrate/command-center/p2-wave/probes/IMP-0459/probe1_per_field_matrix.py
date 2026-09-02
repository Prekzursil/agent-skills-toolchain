#!/usr/bin/env python3
"""Named probe 1: re-run the per-field matrix against the live strict parser.

Independent of emit_receipt's recorded table: rebuild every cell, require the
verbatim rejection to name each rejected field, and require the receipt's
answer set to match this live run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from matrix import PLANTED, build_matrix  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0459.json"
SENTINEL = "SENTINEL:IMP-0459:MANIFEST-STRICT-CLEAN"
MUST_REJECT_PLUGIN = {
    "_generated",
    "rules",
    PLANTED,
    "x-custom",
    "changelog",
}
MUST_ACCEPT_PLUGIN = {"version", "description", "author", "metadata", "hooks"}
MUST_REJECT_MARKET = {"_generated", "plugin_id", PLANTED, "x-custom"}
MUST_ACCEPT_MARKET = {"description", "version", "metadata"}


def _names(msg: str, field: str) -> bool:
    return field in (msg or "")


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 128:
        print("FAILED:IMP-0459-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:IMP-0459-probe1 sentinel-absent")
        return 1
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0459-probe1 self-declared:{state}")
        return 1

    live = build_matrix()
    rec_plugin = set(doc.get("answer", {}).get("plugin_rejected") or [])
    rec_market = set(doc.get("answer", {}).get("marketplace_rejected") or [])
    live_plugin = set(live["rejected_plugin_fields"])
    live_market = set(live["rejected_marketplace_fields"])
    if rec_plugin != live_plugin or rec_market != live_market:
        print("FAILED:IMP-0459-probe1 live matrix disagrees with receipt answer")
        print("plugin delta", sorted(rec_plugin ^ live_plugin))
        print("market delta", sorted(rec_market ^ live_market))
        return 1

    by_p = {r["field"]: r for r in live["plugin"]}
    by_m = {r["field"]: r for r in live["marketplace"]}
    for field in MUST_ACCEPT_PLUGIN:
        if not by_p[field]["accepted"]:
            print(f"FAILED:IMP-0459-probe1 known plugin field rejected: {field}")
            return 1
    for field in MUST_ACCEPT_MARKET:
        if not by_m[field]["accepted"]:
            print(f"FAILED:IMP-0459-probe1 known marketplace field rejected: {field}")
            return 1
    for field in MUST_REJECT_PLUGIN:
        row = by_p[field]
        if row["accepted"] or not _names(row["rejection_message"] or "", field):
            print(f"FAILED:IMP-0459-probe1 plugin reject/name {field} {row}")
            return 1
        print(f"plugin field={field} accepted=False msg={row['rejection_message']}")
    for field in MUST_REJECT_MARKET:
        row = by_m[field]
        if row["accepted"] or not _names(row["rejection_message"] or "", field):
            print(f"FAILED:IMP-0459-probe1 market reject/name {field} {row}")
            return 1
        print(f"marketplace field={field} accepted=False msg={row['rejection_message']}")

    print(
        json.dumps(
            {
                "probe": "probe1-per-field-matrix",
                "unit_id": "IMP-0459",
                "plugin_rejected": sorted(live_plugin),
                "marketplace_rejected": sorted(live_market),
                "cells": len(live["plugin"]) + len(live["marketplace"]),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0459-probe1 per-field matrix re-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
