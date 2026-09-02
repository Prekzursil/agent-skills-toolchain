#!/usr/bin/env python3
"""Probe 1: load/edit/save round-trip on all 72 measured presets (IMP-0328).

Evidence A: field-level diff per preset, only the edited dial path differs.
Evidence B: canonical (order-preserving) hashes of the other 71 presets match.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.presets.catalog import ensure_catalog  # noqa: E402
from tools.council.presets.store import PresetStore  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0328.json"
SENTINEL = "SUCCESS:IMP-0328"


def main() -> int:
    ensure_catalog()
    store = PresetStore()
    presets = store.presets()
    if len(presets) != 72:
        print(f"FAILED:IMP-0328-probe1 catalog count {len(presets)}")
        return 1

    rows = []
    for item in presets:
        ev = store.round_trip_one(item["id"])
        rows.append(ev)
        if not ev["fidelity_ok"]:
            print(json.dumps(ev, indent=2, default=str)[:2000])
            print(f"FAILED:IMP-0328-probe1 fidelity {item['id']}")
            return 1
        if ev["unexpected"]:
            print(json.dumps(ev["unexpected"], indent=2, default=str)[:2000])
            print(f"FAILED:IMP-0328-probe1 leaked fields {item['id']}")
            return 1
        if not ev["untouched_all_match"]:
            print(f"FAILED:IMP-0328-probe1 untouched hash drift {item['id']}")
            return 1
        if not ev["edited_hash_changed"]:
            print(f"FAILED:IMP-0328-probe1 edited hash unchanged {item['id']}")
            return 1

    receipt_ok = None
    if RECEIPT.is_file() and RECEIPT.stat().st_size > 0:
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        state = str(doc.get("state") or doc.get("status") or "").upper()
        receipt_ok = (
            SENTINEL in text
            and state not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
            and str(doc.get("unit_id") or doc.get("id") or "") == "IMP-0328"
        )
        if not receipt_ok:
            print("FAILED:IMP-0328-probe1 receipt missing sentinel or blocked")
            return 1

    payload = {
        "probe": "probe1-roundtrip",
        "unit_id": "IMP-0328",
        "preset_count": len(rows),
        "all_fidelity_ok": True,
        "all_untouched_hashes_match": True,
        "edited_key_only": True,
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
        "sample": [
            {
                "preset_id": rows[0]["preset_id"],
                "dial": rows[0]["dial"],
                "diffs": rows[0]["diffs"],
            },
            {
                "preset_id": rows[-1]["preset_id"],
                "dial": rows[-1]["dial"],
                "diffs": rows[-1]["diffs"],
            },
        ],
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"round_trip 72/72 fidelity_ok edited_key_only untouched_hashes_match")
    print("SUCCESS:IMP-0328-probe1 load/edit/save round-trip on all 72 presets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
