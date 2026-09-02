#!/usr/bin/env python3
"""Probe 2: a direct file open (not the writer) is caught as unregistered.

Both-states: writer-only run is silent; after bypass the sweep fires.
Negative control: trusting writer.emitted_paths (in-memory) misses the bypass;
the disk reconcile does not. The sweep must not auto-register the sneaked file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import UNIT, run_bypass  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0454.json"
SENTINEL = "SENTINEL:IMP-0454:MANIFEST-AUTO-REGISTERED"


def check_receipt() -> str:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt-missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return "receipt-unparseable"
    if not isinstance(doc, dict):
        return "receipt-not-object"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    if SENTINEL not in text:
        return "sentinel-absent"
    if doc.get("bypass_caught") is not True:
        return "receipt-bypass-not-caught"
    return "ok"


def main() -> int:
    result = run_bypass()
    receipt = check_receipt()
    payload = {
        "probe": "probe2-bypass",
        "unit_id": UNIT,
        "before_empty": result["before_empty"],
        "caught": result["caught"],
        "unregistered_count_after": result["unregistered_count_after"],
        "bypass_path": result["bypass_path"],
        "in_memory_misses_bypass": result["in_memory_misses_bypass"],
        "sweep_did_not_register": result["sweep_did_not_register"],
        "both_states": result["both_states"],
        "library_unregistered": result["library_unregistered"],
        "independent_unregistered": result["independent_unregistered"],
        "receipt": receipt,
        "pass": (
            result["caught"]
            and result["both_states"]
            and result["in_memory_misses_bypass"]
            and result["sweep_did_not_register"]
            and result["unregistered_count_after"] == 1
            and receipt == "ok"
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not result["before_empty"]:
        print("FAILED:IMP-0454-probe2 writer-only state was not empty")
        return 1
    if not result["caught"]:
        print("FAILED:IMP-0454-probe2 bypass was not reported unregistered")
        return 1
    if not result["in_memory_misses_bypass"]:
        print("FAILED:IMP-0454-probe2 in-memory writer claim already listed the bypass")
        return 1
    if not result["sweep_did_not_register"]:
        print("FAILED:IMP-0454-probe2 reconcile auto-registered the bypass (later sweep)")
        return 1
    if receipt != "ok":
        print(f"FAILED:IMP-0454-probe2 receipt {receipt}")
        return 1
    print(
        f"before_empty={result['before_empty']} caught={result['caught']} "
        f"unregistered_count={result['unregistered_count_after']} "
        f"memory_missed={result['in_memory_misses_bypass']}"
    )
    print("SUCCESS:IMP-0454-probe2 direct-open bypass caught as unregistered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
