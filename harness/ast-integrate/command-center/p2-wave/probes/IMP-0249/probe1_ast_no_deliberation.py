#!/usr/bin/env python3
"""Probe 1: customer-council contains no embedded deliberation loop (AST).

Both-states: the live consumer is silent; a planted round/participant loop fires.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from ast_scan import scan_path, scan_tree  # noqa: E402

CONSUMER = REPO / "tools" / "blueprints" / "product" / "customer_council"
PLANTED = HERE / "fixtures" / "planted_deliberation_loop.py"
ART = REPO / "command-center" / "receipts" / "IMP-0249.json"


def main() -> int:
    live = scan_tree(CONSUMER)
    planted = scan_path(PLANTED)
    if live["has_deliberation_loop"]:
        print("FAILED:IMP-0249-probe1 live consumer contains a deliberation loop")
        print(json.dumps(live, indent=2)[:4000])
        return 1
    if not planted["has_deliberation_loop"]:
        print("FAILED:IMP-0249-probe1 planted loop did not fire (detector vacuous)")
        print(json.dumps(planted, indent=2)[:4000])
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0249-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:IMP-0249" not in blob:
        print("FAILED:IMP-0249-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0249-probe1 self-declared {doc.get('state')}")
        return 1
    out = {
        "probe": "probe1-ast-no-deliberation",
        "unit_id": "IMP-0249",
        "pass": True,
        "live_files_scanned": live["file_count"],
        "live_hits": live["hits"],
        "planted_fired": True,
        "planted_kinds": sorted({h["kind"] for h in planted["hits"]}),
        "both_states": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"live_hits={len(live['hits'])} planted_fired=True files={live['file_count']}"
    )
    print("SUCCESS:IMP-0249-probe1 no embedded deliberation loop (AST)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
