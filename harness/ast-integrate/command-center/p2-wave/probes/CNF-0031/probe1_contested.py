#!/usr/bin/env python3
"""Named probe 1: live contested dispatch. Re-derive the verdict before reading it.

Signal 1: receipt files on disk. Signal 2: caller return statuses. They must agree
at exactly one execution. The loser must return ALREADY-CLAIMED text, not silence.
Mutation: os.rename publish (exclusive=False) must not reproduce the exclusive
one-winner / one-loser pair (vacuity control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from dispatch import run_contested  # noqa: E402
from schema_ctl import payload_of  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0031-duplicate-dispatch.json"
SENTINEL_NEEDLE = "SUCCESS:CNF-0031 emitted only when the artifact at output_path exists"


def main() -> int:
    live = run_contested(exclusive=True)
    print(
        "live_contested "
        f"receipts={live['execution_count']} "
        f"returns={live['executed_from_returns']} "
        f"winner={live['winner_session_id']} "
        f"loser={live['loser_session_id']} "
        f"loser_status={live['loser_status']}"
    )
    if live["execution_count"] != 1:
        print(f"FAILED:CNF-0031-probe1 contested execution_count={live['execution_count']}")
        return 1
    if not live["signals_agree"]:
        print("FAILED:CNF-0031-probe1 receipt/return disagreement")
        return 1
    if live["loser_status"] != "ALREADY-CLAIMED":
        print(f"FAILED:CNF-0031-probe1 silent-no-op status={live['loser_status']}")
        return 1
    if not live.get("loser_response") or "ALREADY-CLAIMED" not in str(live["loser_response"]):
        print("FAILED:CNF-0031-probe1 loser response not distinguishable")
        return 1
    if live["winner_session_id"] == live["loser_session_id"]:
        print("FAILED:CNF-0031-probe1 winner equals loser")
        return 1

    mutant = run_contested(exclusive=False)
    print(
        "mutation_rename "
        f"receipts={mutant['execution_count']} "
        f"returns={mutant['executed_from_returns']} "
        f"loser_status={mutant.get('loser_status')}"
    )
    if mutant["execution_count"] != 2:
        print(
            "FAILED:CNF-0031-probe1 rename mutation did not produce two executions "
            f"(vacuity control) count={mutant['execution_count']}"
        )
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0031-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL_NEEDLE not in text:
        print("FAILED:CNF-0031-probe1 completion sentinel absent")
        return 1
    if doc.get("unit_id") != "CNF-0031":
        print("FAILED:CNF-0031-probe1 unit_id")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0031-probe1 self-declared {doc.get('state')}")
        return 1
    payload = payload_of(doc)
    contested = payload.get("contested") or doc.get("contested") or {}
    counts = payload.get("execution_counts") or doc.get("execution_counts") or {}
    if contested.get("execution_count") != 1:
        print("FAILED:CNF-0031-probe1 artifact contested count")
        return 1
    if contested.get("loser_status") != "ALREADY-CLAIMED":
        print("FAILED:CNF-0031-probe1 artifact loser_status")
        return 1
    if counts.get("contested") != 1:
        print("FAILED:CNF-0031-probe1 execution_counts.contested")
        return 1
    print("SUCCESS:CNF-0031-probe1 contested one-execution already-claimed loser")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
