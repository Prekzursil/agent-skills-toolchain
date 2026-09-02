#!/usr/bin/env python3
"""Probe 1: detector control — the canary writes a marker when run directly.

Mechanically independent of the installer: subprocess the same postinstall.py
the package ships. Implicit install must leave the host marker absent; the
naive execute-on-host control must write it (both-states, not a constant).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.install import (  # noqa: E402
    HANDLING_NAIVE_HOST,
    HANDLING_REFUSED_IMPLICIT,
    measure_postinstall_policy,
)

RECEIPT = REPO / "command-center" / "receipts" / "TST-0217.json"
SENTINEL = "SUCCESS:TST-0217"


def _receipt_ok() -> bool | None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return None
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    ev = doc.get("evidence_requirement") or {}
    det = ev.get("a_canary_marker_absent_on_host") or {}
    return (
        str(doc.get("state") or "").upper()
        not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
        and SENTINEL in text
        and det.get("implicit_host_marker_present") is False
        and det.get("detector_direct_wrote_marker") is True
        and det.get("naive_host_marker_present") is True
    )


def main() -> int:
    live = measure_postinstall_policy()
    receipt_ok = _receipt_ok()
    detector = live.get("detector_direct") or {}
    implicit = live.get("implicit_install") or {}
    naive = live.get("naive_host_execute") or {}
    ok = (
        bool(live.get("pass"))
        and bool(live.get("detector_pass"))
        and bool(detector.get("pass"))
        and implicit.get("handling") == HANDLING_REFUSED_IMPLICIT
        and naive.get("handling") == HANDLING_NAIVE_HOST
        and live.get("implicit_host_marker_present") is False
        and live.get("naive_host_marker_present") is True
        and (receipt_ok is not False)
    )
    payload = {
        "probe": "probe1-detector-control",
        "unit_id": "TST-0217",
        "method": "direct-subprocess-canary",
        "data_field": "cwd_marker_present+host_marker_present",
        "measurement_kind": "canary-direct-vs-implicit-vs-naive",
        "pass": ok,
        "live": {
            "detector_pass": live.get("detector_pass"),
            "detector_cwd_marker": detector.get("cwd_marker_present"),
            "detector_host_marker": detector.get("host_marker_present"),
            "implicit_handling": implicit.get("handling"),
            "implicit_executed": implicit.get("executed"),
            "implicit_host_marker_present": live.get("implicit_host_marker_present"),
            "naive_handling": naive.get("handling"),
            "naive_host_marker_present": live.get("naive_host_marker_present"),
            "both_states": live.get("both_states"),
            "pass": live.get("pass"),
        },
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not detector.get("pass"):
        print("FAILED:TST-0217-probe1 direct canary did not write its marker")
        return 1
    if implicit.get("handling") != HANDLING_REFUSED_IMPLICIT:
        print(f"FAILED:TST-0217-probe1 implicit handling={implicit.get('handling')}")
        return 1
    if live.get("implicit_host_marker_present"):
        print("FAILED:TST-0217-probe1 implicit install wrote a host marker")
        return 1
    if not live.get("naive_host_marker_present"):
        print("FAILED:TST-0217-probe1 naive control did not write a host marker")
        return 1
    if not live.get("both_states"):
        print("FAILED:TST-0217-probe1 both-states failed (marker presence is a constant)")
        return 1
    if receipt_ok is False:
        print("FAILED:TST-0217-probe1 receipt does not match live detector control")
        return 1
    print(
        f"direct={detector.get('cwd_marker_present')} "
        f"implicit_host={live.get('implicit_host_marker_present')} "
        f"naive_host={live.get('naive_host_marker_present')}"
    )
    print("SUCCESS:TST-0217-probe1 canary writes when run directly; implicit install does not")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
