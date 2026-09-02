#!/usr/bin/env python3
"""Probe 2: re-run planted RESOLVE + ACYCLIC detector controls."""
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
    planted = r["planted"]
    resolve = r["checks"]["RESOLVE"]
    acyclic = r["checks"]["ACYCLIC"]
    payload = {
        "probe": "probe2-detector-controls",
        "unit_id": "ADV-0134",
        "broken_chain_fired": planted["broken_chain_fired"],
        "cycle_fired": planted["cycle_fired"],
        "same_run_as_counts": planted["same_run_as_counts"],
        "RESOLVE_count": resolve["count"],
        "ACYCLIC_count": acyclic["count"],
        "acyclic_steps": r.get("acyclic_steps"),
        "elapsed_ms": r["elapsed_ms"],
        "hung": False,
    }
    print(json.dumps(payload, sort_keys=True))
    if r["elapsed_ms"] > 30_000:
        print("FAILED:ADV-0134-probe2 walker too slow; treat as hang")
        return 1
    if not planted["broken_chain_fired"]:
        print("FAILED:ADV-0134-probe2 planted broken chain did not fire RESOLVE")
        return 1
    if not planted["cycle_fired"]:
        print("FAILED:ADV-0134-probe2 planted cycle did not fire ACYCLIC")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0134-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0134-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ADV-0134" not in text:
        print("FAILED:ADV-0134-probe2 sentinel absent")
        return 1
    print(
        f"broken_fired={planted['broken_chain_fired']} "
        f"cycle_fired={planted['cycle_fired']} "
        f"RESOLVE={resolve['count']} ACYCLIC={acyclic['count']} "
        f"steps={r.get('acyclic_steps')} elapsed_ms={r['elapsed_ms']}"
    )
    print("SUCCESS:ADV-0134-probe2 planted RESOLVE and ACYCLIC fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
