#!/usr/bin/env python3
"""Probe 2: inferred anchors require a named source; independent corpus recount."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from controls import test_inferred_anchor_requires_a_named_source  # noqa: E402
from corpus import resolve_corpus  # noqa: E402

REPO = HERE.parents[3]
RECEIPT = REPO / "command-center" / "receipts" / "TST-0009.json"


def main() -> int:
    t_inf = test_inferred_anchor_requires_a_named_source(REPO)
    live = resolve_corpus(REPO)
    snap = live.get("snapshot") or {}
    snap_ok = bool(snap.get("present"))
    receipt_ok = True
    receipt_note = "receipt-absent"
    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        published = doc.get("resolution") or {}
        state = str(doc.get("state") or "").upper()
        receipt_ok = (
            doc.get("unit_id") == "TST-0009"
            and state not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
            and "SUCCESS:TST-0009" in text
            and int(published.get("fail_to_resolve_count", -1)) == live["fail_to_resolve_count"]
            and int(published.get("anchor_count", -1)) == live["anchor_count"]
            and published.get("counts_by_kind") == live["counts_by_kind"]
            and published.get("counts_by_outcome") == live["counts_by_outcome"]
            and bool((published.get("snapshot") or {}).get("present"))
        )
        if not snap_ok:
            receipt_note = "snapshot-absent"
        elif receipt_ok:
            receipt_note = "receipt-counts-match-frozen-harvest"
        else:
            receipt_note = "receipt-count-mismatch"
    else:
        receipt_ok = False
        if not snap_ok:
            receipt_note = "snapshot-absent"

    passed = bool(t_inf["pass"] and receipt_ok and snap_ok)
    payload = {
        "probe": "probe2-inferred-named-source-and-corpus-recount",
        "unit_id": "TST-0009",
        "pass": passed,
        "test_inferred_anchor_requires_a_named_source": t_inf["pass"],
        "named_inferred_resolved": t_inf["named"]["outcome"] == "resolved",
        "unnamed_inferred_unresolved": t_inf["empty_source"]["outcome"] == "unresolved",
        "receipt_ok": receipt_ok,
        "receipt_note": receipt_note,
        "live_anchor_count": live["anchor_count"],
        "live_fail_to_resolve_count": live["fail_to_resolve_count"],
        "live_counts_by_kind": live["counts_by_kind"],
        "live_counts_by_outcome": live["counts_by_outcome"],
        "registry_present": live["registry"]["present"],
        "corpus_name": live["corpus_name"],
        "snapshot_present": bool((live.get("snapshot") or {}).get("present")),
        "snapshot_path": (live.get("snapshot") or {}).get("path"),
        "snapshot_frozen_at": (live.get("snapshot") or {}).get("frozen_at"),
    }
    print(json.dumps(payload, sort_keys=True))
    if not passed:
        print("FAILED:TST-0009-probe2 inferred-named-source or corpus recount")
        return 1
    print(
        "SUCCESS:TST-0009-probe2 inferred requires a named source; "
        f"live fail_to_resolve={live['fail_to_resolve_count']}/{live['anchor_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
