#!/usr/bin/env python3
"""Probe 1: prove the egress block is live; silent-download tests go red cold.

Signal is the unshare -n control-fetch OSError, plus blocked-cold outcomes.
Probe 2 reads both-states restore and the warm-cache mask — a different field.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from egress import LocalOrigin, prove_block  # noqa: E402
from matrix import run_matrix  # noqa: E402
from suite import SILENT_COUNT  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0147.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0147-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0147":
        print("FAILED:CNF-0147-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0147-probe1 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:CNF-0147" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0147-probe1 sentinel absent")
        return 1

    origin = LocalOrigin()
    port = origin.start()
    try:
        live_block = prove_block(port)
    finally:
        origin.stop()
    if not live_block["pass"]:
        print("FAILED:CNF-0147-probe1 live block control")
        print(json.dumps(live_block, indent=2, default=str)[:2000])
        return 1
    if live_block["unblocked_ok"] is not True:
        print("FAILED:CNF-0147-probe1 unblocked control fetch did not succeed")
        return 1
    if live_block["blocked_ok"] is not False:
        print("FAILED:CNF-0147-probe1 blocked control fetch did not fail")
        return 1
    err = str(live_block.get("blocked_error") or "")
    if "unreachable" not in err.lower() and "101" not in err:
        print("FAILED:CNF-0147-probe1 blocked error not ENETUNREACH", err)
        return 1

    live = run_matrix()
    silent = live["attribution"]["silent_download"]
    declared = live["attribution"]["declared_dependency"]
    if live["attribution"]["unknown"]:
        print("FAILED:CNF-0147-probe1 unknown bucket", live["attribution"]["unknown"])
        return 1
    if len(silent) != SILENT_COUNT:
        print(f"FAILED:CNF-0147-probe1 silent={len(silent)} want={SILENT_COUNT}")
        return 1
    if len(declared) != 2:
        print(f"FAILED:CNF-0147-probe1 declared={len(declared)} want=2")
        return 1

    rec_block = doc.get("block_control") or {}
    if rec_block.get("unblocked_ok") is not True or rec_block.get("blocked_ok") is not False:
        print("FAILED:CNF-0147-probe1 artifact block_control drift")
        return 1
    rec_silent = list((doc.get("attribution") or {}).get("silent_download") or [])
    if sorted(rec_silent) != sorted(silent):
        print("FAILED:CNF-0147-probe1 artifact silent set != live")
        print("artifact", rec_silent)
        print("live", silent)
        return 1

    blocked_cold = next(r for r in live["runs"] if r["id"] == "blocked-cold")
    by = {row["id"]: row for row in blocked_cold["results"]}
    for test_id in silent:
        if by[test_id]["ok"]:
            print(f"FAILED:CNF-0147-probe1 silent {test_id} passed under blocked-cold")
            return 1
        attempts = by[test_id].get("attempts") or []
        if not attempts:
            print(f"FAILED:CNF-0147-probe1 silent {test_id} recorded no connection attempt")
            return 1

    out = {
        "probe": "probe1-block-control",
        "unit_id": "CNF-0147",
        "unblocked_ok": True,
        "blocked_ok": False,
        "blocked_error": err,
        "silent_download_n": len(silent),
        "declared_dependency_n": len(declared),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"control unblocked=True blocked=False error={err!r} "
        f"silent={len(silent)} declared={len(declared)}"
    )
    print("SUCCESS:CNF-0147-probe1 block control and silent-download red set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
