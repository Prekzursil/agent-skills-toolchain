#!/usr/bin/env python3
"""Probe 2: quarantine excludes contaminated cases from a score recomputation.

Mechanically different from probe 1 (which only asserts detection): every
control case is an oracle PASS, scoring without quarantine is 3/3, scoring
with quarantine of ALPHA+BETA is 1/1 (GAMMA only). Both-states: the dirty
score still counts the contaminated cases, proving the inflation is visible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center"))

from bench.contamination import (  # noqa: E402
    ALPHA_ID,
    BETA_ID,
    GAMMA_ID,
    measure_detector_control,
)

RECEIPT = REPO / "command-center" / "receipts" / "TST-0307.json"
SENTINEL = "SUCCESS:TST-0307"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0307-probe2 {msg}")
    return 1


def main() -> int:
    ctrl = measure_detector_control()
    dirty = ctrl.get("score_without_quarantine") or {}
    clean = ctrl.get("score_with_quarantine") or {}
    qids = list(ctrl.get("quarantine_ids") or [])
    ok = (
        ctrl.get("pass") is True
        and ctrl.get("quarantine_changes_score") is True
        and float(ctrl.get("points_delta") or 0) == 2.0
        and dirty.get("n_scored") == 3
        and dirty.get("points") == 3.0
        and clean.get("n_scored") == 1
        and clean.get("points") == 1.0
        and GAMMA_ID in (clean.get("scored_ids") or [])
        and ALPHA_ID not in (clean.get("scored_ids") or [])
        and BETA_ID not in (clean.get("scored_ids") or [])
        and ALPHA_ID in qids
        and BETA_ID in qids
        and GAMMA_ID not in qids
        # both-states: dirty still includes contaminated passes
        and ALPHA_ID in (dirty.get("scored_ids") or [])
        and BETA_ID in (dirty.get("scored_ids") or [])
    )
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    q = doc.get("quarantine_effect") or {}
    receipt_ok = (
        str(doc.get("state") or "").upper()
        not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
        and SENTINEL in text
        and q.get("quarantine_changes_score") is True
        and float(q.get("points_delta") or 0) == 2.0
        and (q.get("without_quarantine") or {}).get("n_scored") == 3
        and (q.get("with_quarantine") or {}).get("n_scored") == 1
    )
    payload = {
        "probe": "probe2-quarantine",
        "unit_id": "TST-0307",
        "pass": bool(ok and receipt_ok),
        "quarantine_ids": qids,
        "without_quarantine": dirty,
        "with_quarantine": clean,
        "points_delta": ctrl.get("points_delta"),
        "quarantine_changes_score": ctrl.get("quarantine_changes_score"),
        "receipt_ok": receipt_ok,
        "both_states": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        return fail("quarantine score recomputation miss")
    if not receipt_ok:
        return fail("receipt mismatch")
    print(
        f"dirty={dirty.get('n_scored')}/3 clean={clean.get('n_scored')}/1 "
        f"delta={ctrl.get('points_delta')} excluded={qids}"
    )
    print("SUCCESS:TST-0307-probe2 quarantine excludes contaminated cases from score")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
