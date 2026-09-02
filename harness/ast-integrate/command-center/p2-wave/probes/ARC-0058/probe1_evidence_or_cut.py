#!/usr/bin/env python3
"""Probe 1: reproduce evidence-or-cut + ranking on the live ledger.

Both-states: live ledger yields ERROR-REDUCING survivors and COSMETIC cuts;
an empty ledger classifies every item COSMETIC (never UNPROVEN).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A8/REFUTATION.json"


def main() -> int:
    run = S.run_scenario()
    slim = {k: run[k] for k in sorted(run) if k not in {"live", "empty_ledger"}}
    print(json.dumps(slim, sort_keys=True, default=str))
    if not run.get("pass"):
        print("FAILED:ARC-0058-probe1 scenario did not reproduce")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0058-probe1 REFUTATION.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:ARC-0058-probe1 self-declared {doc.get('state')}")
        return 1
    rec = (doc.get("scenario") or {}).get("reproduction") or {}
    rec_ok = (
        rec.get("live_mixed_classes") is True
        and rec.get("empty_ledger_all_cosmetic") is True
        and rec.get("unproven_rejected") is True
        and rec.get("organizing_principle_would_fund_cosmetic") is True
    )
    if not rec_ok:
        print("FAILED:ARC-0058-probe1 REFUTATION reproduction flags false")
        return 1
    proc = doc.get("scenario", {}).get("procedure") or []
    if len(proc) < 4:
        print("FAILED:ARC-0058-probe1 procedure too short")
        return 1
    if not run.get("cosmetic_ids") or not run.get("ranked_ids"):
        print("FAILED:ARC-0058-probe1 expected mixed classes")
        return 1
    if run.get("empty_unproven_present"):
        print("FAILED:ARC-0058-probe1 empty ledger emitted UNPROVEN")
        return 1
    cut = doc.get("evidence_or_cut") or {}
    if cut.get("unproven_rejected") is not True:
        print("FAILED:ARC-0058-probe1 artifact did not reject UNPROVEN")
        return 1
    print(
        "mixed="
        f"{bool(run.get('cosmetic_ids') and run.get('ranked_ids'))} "
        f"empty_cosmetic={bool(run.get('empty_all_cosmetic'))} "
        f"unproven_rejected={bool(run.get('unproven_rejected'))}"
    )
    print("SUCCESS:ARC-0058-probe1 evidence-or-cut scenario reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
