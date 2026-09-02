#!/usr/bin/env python3
"""Probe 1: truncated entry is quarantined; intact sibling is not.

Signal (1) of the catalog evidence_requirement: quarantine directory listing
names the truncated plugin and does not name the intact one.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
REAPER = REPO / "tools" / "plugin-cache-reaper"
sys.path.insert(0, str(REAPER))
from cache import PAYLOAD_NAME, PluginCache  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0041.json"


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        print("FAILED:IMP-0041-probe1 receipt missing")
        return 1
    text = RECEIPT.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0041" not in text:
        print("FAILED:IMP-0041-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0041-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0041-p1-") as tmp:
        cache = PluginCache(tmp)
        intact = b"intact-plugin-source-AAAA"
        truncated_src = b"truncated-plugin-source-BBBB"
        cache.put("intactplug", "1.0.0", intact, scope="site")
        key = cache.put("truncplug", "1.0.0", truncated_src, scope="site")
        payload = cache.entry_dir(key) / PAYLOAD_NAME
        payload.write_bytes(truncated_src[:9])
        report = cache.refresh(scope="site")
        listing = cache.quarantine_listing()

    q_ids = {row["plugin_id"] for row in report.quarantined}
    intact_ids = {row["plugin_id"] for row in report.intact}
    if "truncplug" not in q_ids:
        print("FAILED:IMP-0041-probe1 truncated plugin not quarantined", report.as_dict())
        return 1
    if "intactplug" in q_ids:
        print("FAILED:IMP-0041-probe1 intact plugin was quarantined (negative control)")
        return 1
    if "intactplug" not in intact_ids:
        print("FAILED:IMP-0041-probe1 intact plugin missing from intact set")
        return 1
    if not any("truncplug" in name for name in listing):
        print("FAILED:IMP-0041-probe1 quarantine listing lacks truncplug", listing)
        return 1
    if any("intactplug" in name for name in listing):
        print("FAILED:IMP-0041-probe1 quarantine listing names intact plugin", listing)
        return 1

    out = {
        "probe": "probe1-quarantine-listing",
        "unit_id": "IMP-0041",
        "quarantine_listing": listing,
        "quarantined_plugin_ids": sorted(q_ids),
        "intact_plugin_ids": sorted(intact_ids),
        "truncated_named_in_listing": True,
        "intact_absent_from_listing": True,
        "pass": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0041-probe1 truncated quarantined; intact sibling not")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
