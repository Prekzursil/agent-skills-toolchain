#!/usr/bin/env python3
"""Named probe 2: planted-orphan detector plus live listing recompute."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from reconcile import (  # noqa: E402
    PLANTED_ORPHAN_ID,
    live_reconcile,
)
from tests_required import test_reconciler_finds_a_planted_orphan  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0123.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0123-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0123-probe2 unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:TST-0123-probe2 receipt not an object")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0123-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:TST-0123" not in text:
        print("FAILED:TST-0123-probe2 sentinel absent")
        return 1

    def _count(block: dict, *keys: str) -> int:
        cur: object = block
        for key in keys:
            if not isinstance(cur, dict) or key not in cur:
                raise KeyError(".".join(keys))
            cur = cur[key]
        if type(cur) is not int:
            raise TypeError(f"{'.'.join(keys)} is {type(cur).__name__}")
        return cur

    planted = test_reconciler_finds_a_planted_orphan()
    live = live_reconcile()
    live_block = doc.get("live_reconciliation")
    if not isinstance(live_block, dict):
        print("FAILED:TST-0123-probe2 live_reconciliation missing")
        return 1
    try:
        art_reg = _count(live_block, "registry_count")
        art_col = _count(live_block, "collected_count")
        art_reg_only = _count(live_block, "registry_only", "count")
        art_col_only = _count(live_block, "collected_only", "count")
    except (KeyError, TypeError) as exc:
        print(f"FAILED:TST-0123-probe2 live_reconciliation fields {exc}")
        return 1
    if art_reg != live["registry_count"]:
        print(
            "FAILED:TST-0123-probe2 live registry_count drift",
            art_reg,
            live["registry_count"],
        )
        return 1
    if art_col != live["collected_count"]:
        print(
            "FAILED:TST-0123-probe2 live collected_count drift",
            art_col,
            live["collected_count"],
        )
        return 1
    if art_reg_only != live["registry_only"]["count"]:
        print("FAILED:TST-0123-probe2 live registry_only count drift")
        return 1
    if art_col_only != live["collected_only"]["count"]:
        print("FAILED:TST-0123-probe2 live collected_only count drift")
        return 1
    if "COLLECTED " not in live["listing"]:
        print("FAILED:TST-0123-probe2 live listing is not runner output")
        return 1
    if planted["planted"]["registry_only"]["ids"] != [PLANTED_ORPHAN_ID]:
        print("FAILED:TST-0123-probe2 planted orphan not isolated")
        return 1
    payload = {
        "probe": "probe2-planted-orphan-and-live",
        "unit_id": "TST-0123",
        "planted_orphan": PLANTED_ORPHAN_ID,
        "planted_registry_only_count": planted["planted"]["registry_only"]["count"],
        "live_registry_count": live["registry_count"],
        "live_collected_count": live["collected_count"],
        "live_registry_only_count": live["registry_only"]["count"],
        "live_collected_only_count": live["collected_only"]["count"],
        "registry_present": live["registry"]["present"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "planted",
        PLANTED_ORPHAN_ID,
        "live registry_only",
        live["registry_only"]["count"],
        "collected_only",
        live["collected_only"]["count"],
    )
    print("SUCCESS:TST-0123-probe2 planted orphan found; live listing recomputes both counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
