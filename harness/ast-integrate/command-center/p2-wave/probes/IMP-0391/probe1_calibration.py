#!/usr/bin/env python3
"""Probe 1: reliability diagram + Brier on the labelled corpus.

Recomputes the diagram from the live fusion, then (if the receipt exists)
checks that the published bins and Brier score rederive. A 0.9 band that
does not contain about 90 percent correct selections fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PKG = REPO / "tools" / "router"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from corpus import PROD_WEIGHTS, evaluate  # noqa: E402
from fusion import CALIBRATION_TOLERANCE  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0391.json"
SENTINEL = "SENTINEL:IMP-0391:FUSION-CALIBRATED"


def _close(a, b, tol: float = 1e-6) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    live = evaluate(w_det=PROD_WEIGHTS["w_det"], w_sem=PROD_WEIGHTS["w_sem"])
    outliers = live["named_outlier_bins"]
    band90 = [b for b in live["band_0_9"] if int(b["n"]) > 0]
    bins_ok = not outliers
    acc_ok = live["accuracy"] >= 0.75
    band_ok = bool(band90)
    if band90:
        # 0.9 band: observed accuracy must sit within 0.15 of the predicted
        # confidence (the catalog's named tolerance).
        band_ok = all(
            (b["delta"] is None) or (float(b["delta"]) <= CALIBRATION_TOLERANCE)
            for b in band90
        )

    receipt_ok = None
    receipt_rederives = None
    if RECEIPT.is_file() and RECEIPT.stat().st_size > 0:
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        published = (doc.get("calibration") or {}).get("reliability_diagram") or []
        pub_brier = (doc.get("calibration") or {}).get("brier_score")
        st = str(doc.get("state") or "").upper()
        receipt_ok = (
            st not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
            and SENTINEL in text
            and isinstance(published, list)
            and published
        )
        if published and pub_brier is not None:
            live_bins = live["reliability_diagram"]
            same_len = len(published) == len(live_bins)
            same_n = same_len and all(
                int(a.get("n") or 0) == int(b.get("n") or 0)
                for a, b in zip(published, live_bins)
            )
            same_obs = same_len and all(
                _close(a.get("observed_accuracy"), b.get("observed_accuracy"))
                for a, b in zip(published, live_bins)
            )
            same_brier = _close(pub_brier, live["brier"], tol=1e-6)
            receipt_rederives = bool(same_n and same_obs and same_brier)
            receipt_ok = bool(receipt_ok) and receipt_rederives

    passed = bins_ok and acc_ok and band_ok and (receipt_ok is not False)
    payload = {
        "probe": "probe1-calibration",
        "unit_id": "IMP-0391",
        "n": live["n"],
        "n_correct": live["n_correct"],
        "accuracy": round(live["accuracy"], 6),
        "brier_score": round(live["brier"], 6),
        "tolerance": CALIBRATION_TOLERANCE,
        "reliability_diagram": live["reliability_diagram"],
        "named_outlier_bins": outliers,
        "band_0_9": band90,
        "bins_within_tolerance": bins_ok,
        "accuracy_ok": acc_ok,
        "band_0_9_ok": band_ok,
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
        "receipt_rederives": receipt_rederives,
        "pass": passed,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not acc_ok:
        print("FAILED:IMP-0391-probe1 fusion accuracy below 0.75")
        return 1
    if not band_ok:
        print("FAILED:IMP-0391-probe1 0.9 band missing or outside tolerance")
        return 1
    if not bins_ok:
        print("FAILED:IMP-0391-probe1 named outlier bins", outliers)
        return 1
    if receipt_ok is False:
        print("FAILED:IMP-0391-probe1 receipt does not rederive live diagram")
        return 1
    print(
        f"accuracy={live['accuracy']:.4f} brier={live['brier']:.4f} "
        f"outliers={len(outliers)} band90_n={sum(int(b['n']) for b in band90)}"
    )
    print("SUCCESS:IMP-0391-probe1 reliability diagram within tolerance; Brier live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
