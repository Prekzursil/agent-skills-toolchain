#!/usr/bin/env python3
"""Probe 1: both-states resume (before fan-out starts, after it completes).

Also re-runs the two mutants so the detectors are shown to fire on bad
states and stay silent on the good run.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenarios as S  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0168.json"
SENTINEL = "SUCCESS:TST-0168"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _check_artifact() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0168-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0168-probe1 unparseable {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0168-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:TST-0168-probe1 self-declared:{st}")
        return 1
    if doc.get("unit_id") != "TST-0168":
        print("FAILED:TST-0168-probe1 unit_id", doc.get("unit_id"))
        return 1
    both = doc.get("both_states") or {}
    if both.get("ok") is not True:
        print("FAILED:TST-0168-probe1 receipt both_states.ok is not true")
        return 1
    mutants = doc.get("mutants") or {}
    if mutants.get("ok") is not True:
        print("FAILED:TST-0168-probe1 receipt mutants.ok is not true")
        return 1
    return 0


def main() -> int:
    if _check_artifact() != 0:
        return 1
    with tempfile.TemporaryDirectory(prefix="tst0168-p1-") as tmp:
        root = Path(tmp)
        both = S.run_both_states(root / "both")
        mutants = S.run_mutants(root / "mutants")

    payload = {
        "probe": "probe1-both-states",
        "unit_id": "TST-0168",
        "both_states_ok": both.get("ok"),
        "before_fanout_ok": (both.get("before_fanout") or {}).get("ok"),
        "after_complete_ok": (both.get("after_complete") or {}).get("ok"),
        "children_equal_before": (both.get("before_fanout") or {}).get("children_equal"),
        "children_equal_after": (both.get("after_complete") or {}).get("children_equal"),
        "no_extra_receipts": (both.get("after_complete") or {}).get("no_extra_receipts"),
        "mutants_ok": mutants.get("ok"),
        "skip_claim_fired": (mutants.get("skip_claim") or {}).get("fired_on_bad"),
        "double_receipt_fired": (mutants.get("double_receipt") or {}).get("fired_on_bad"),
        "silent_on_good": (mutants.get("silent_on_good") or {}).get("ok"),
        "pass": bool(both.get("ok") and mutants.get("ok")),
    }
    print(json.dumps(payload, sort_keys=True))
    if not both.get("ok"):
        print("FAILED:TST-0168-probe1 both-states resume")
        return 1
    if not mutants.get("ok"):
        print("FAILED:TST-0168-probe1 mutants did not discriminate")
        return 1
    print(
        "before_ok=%s after_ok=%s skip_claim_fired=%s double_receipt_fired=%s"
        % (
            payload["before_fanout_ok"],
            payload["after_complete_ok"],
            payload["skip_claim_fired"],
            payload["double_receipt_fired"],
        )
    )
    print("SUCCESS:TST-0168-probe1 both-states resume; mutants fire on bad, silent on good")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
