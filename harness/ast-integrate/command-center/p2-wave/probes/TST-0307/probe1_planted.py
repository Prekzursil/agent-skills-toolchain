#!/usr/bin/env python3
"""Probe 1: planted verbatim, hash, and paraphrase leaks are found.

Mechanically: build an isolated control tree, run the scanner, require
ALPHA (verbatim + hash), BETA (near-coverage paraphrase), not GAMMA,
and a naive verbatim-only scan that misses BETA. Independent of probe 2
(score recomputation).
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
    print(f"FAILED:TST-0307-probe1 {msg}")
    return 1


def main() -> int:
    ctrl = measure_detector_control()
    ok = (
        ctrl.get("pass") is True
        and ctrl.get("alpha_found") is True
        and ctrl.get("beta_found") is True
        and ctrl.get("gamma_found") is False
        and ctrl.get("naive_alpha") is True
        and ctrl.get("naive_beta") is False
        and ctrl.get("paraphrase_caught") is True
        and ctrl.get("rewrite_caught") is False
        and int(ctrl.get("hash_hits") or 0) >= 1
        and ALPHA_ID in (ctrl.get("quarantine_ids") or [])
        and BETA_ID in (ctrl.get("quarantine_ids") or [])
        and GAMMA_ID not in (ctrl.get("quarantine_ids") or [])
        and int(ctrl.get("n_paths_searched") or 0) >= 4
    )
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    receipt_ok = (
        str(doc.get("state") or "").upper()
        not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
        and SENTINEL in text
        and (doc.get("detector_control") or {}).get("paraphrase_caught") is True
        and (doc.get("detector_control") or {}).get("alpha_found") is True
        and (doc.get("detector_control") or {}).get("gamma_found") is False
    )
    payload = {
        "probe": "probe1-planted",
        "unit_id": "TST-0307",
        "pass": bool(ok and receipt_ok),
        "alpha_found": ctrl.get("alpha_found"),
        "beta_found": ctrl.get("beta_found"),
        "gamma_found": ctrl.get("gamma_found"),
        "naive_beta": ctrl.get("naive_beta"),
        "paraphrase_caught": ctrl.get("paraphrase_caught"),
        "rewrite_caught": ctrl.get("rewrite_caught"),
        "hash_hits": ctrl.get("hash_hits"),
        "n_paths_searched": ctrl.get("n_paths_searched"),
        "contaminated_ids": ctrl.get("quarantine_ids"),
        "receipt_ok": receipt_ok,
        "threshold": ctrl.get("threshold"),
        "method": ctrl.get("method"),
        "near_match_scope": ctrl.get("near_match_scope"),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        return fail("detector-control miss")
    if not receipt_ok:
        return fail("receipt mismatch")
    print(
        "planted ALPHA+BETA found; GAMMA clean; naive misses paraphrase; "
        f"paths={ctrl.get('n_paths_searched')}"
    )
    print("SUCCESS:TST-0307-probe1 planted verbatim/hash/paraphrase control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
