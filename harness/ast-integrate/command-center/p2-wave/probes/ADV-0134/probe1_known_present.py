#!/usr/bin/env python3
"""Probe 1: known-present AgentBridge retirement successor pair."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import graph as G  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0134-supersession-integrity.json"


def main() -> int:
    r = G.evaluate()
    known = r["known_present"]
    payload = {
        "probe": "probe1-known-present",
        "unit_id": "ADV-0134",
        "found": known["found"],
        "successors": known["successors"],
        "edge_count": known["edge_count"],
        "elapsed_ms": r["elapsed_ms"],
    }
    print(json.dumps(payload, sort_keys=True))
    if not known["found"]:
        print("FAILED:ADV-0134-probe1 AgentBridge successor pair not found")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0134-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0134-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ADV-0134" not in text:
        print("FAILED:ADV-0134-probe1 sentinel absent")
        return 1
    print(
        f"agentbridge_found={known['found']} successors={known['successors']} "
        f"edge_count={known['edge_count']}"
    )
    print("SUCCESS:ADV-0134-probe1 known-present AgentBridge successor pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
