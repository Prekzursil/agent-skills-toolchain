#!/usr/bin/env python3
"""Probe 1: both-states write-once receipts.

False-negative timeout retry must leave the terminal receipt unchanged.
A retry of a genuinely FAILED unit must write a new receipt.
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

ART = REPO / "command-center" / "receipts" / "TST-0159.json"
SENTINEL = "SUCCESS:TST-0159"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _check_artifact() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0159-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0159-probe1 unparseable {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0159-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:TST-0159-probe1 self-declared:{st}")
        return 1
    if doc.get("unit_id") != "TST-0159":
        print("FAILED:TST-0159-probe1 unit_id", doc.get("unit_id"))
        return 1
    both = doc.get("both_states") or {}
    if both.get("ok") is not True:
        print("FAILED:TST-0159-probe1 receipt both_states.ok is not true")
        return 1
    fn = both.get("false_negative_timeout") or {}
    if fn.get("write_once_holds") is not True or fn.get("hashes_equal") is not True:
        print("FAILED:TST-0159-probe1 receipt false-negative claim missing")
        return 1
    failed = both.get("genuine_failure_retry") or {}
    if failed.get("wrote_new_receipt") is not True:
        print("FAILED:TST-0159-probe1 receipt genuine-failure claim missing")
        return 1
    return 0


def main() -> int:
    if _check_artifact() != 0:
        return 1
    with tempfile.TemporaryDirectory(prefix="tst0159-p1-") as tmp:
        both = S.run_both_states(Path(tmp) / "both")

    fn = both.get("false_negative_timeout") or {}
    failed = both.get("genuine_failure_retry") or {}
    stale = both.get("stale_cas") or {}
    payload = {
        "probe": "probe1-both-states",
        "unit_id": "TST-0159",
        "both_states_ok": both.get("ok"),
        "fn_write_once_holds": fn.get("write_once_holds"),
        "fn_hashes_equal": fn.get("hashes_equal"),
        "fn_hash_before": fn.get("hash_before"),
        "fn_hash_after": fn.get("hash_after"),
        "fn_second_status": fn.get("second_status"),
        "failed_wrote": failed.get("wrote_new_receipt"),
        "failed_hashes_equal": failed.get("hashes_equal"),
        "stale_cas_ok": stale.get("ok"),
        "pass": bool(both.get("ok")),
    }
    print(json.dumps(payload, sort_keys=True))
    if not both.get("ok"):
        print("FAILED:TST-0159-probe1 both-states write-once")
        return 1
    if not fn.get("write_once_holds"):
        print("FAILED:TST-0159-probe1 false-negative retry overwrote terminal receipt")
        return 1
    if not failed.get("wrote_new_receipt"):
        print("FAILED:TST-0159-probe1 genuine-failure retry did not write")
        return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    art_fn = ((art.get("both_states") or {}).get("false_negative_timeout") or {})
    if art_fn.get("hash_before") != fn.get("hash_before"):
        print("FAILED:TST-0159-probe1 hash_before artifact/live mismatch")
        return 1
    if art_fn.get("hash_after") != fn.get("hash_after"):
        print("FAILED:TST-0159-probe1 hash_after artifact/live mismatch")
        return 1
    print(
        "fn_holds=%s fn_equal=%s failed_wrote=%s stale=%s"
        % (
            fn.get("write_once_holds"),
            fn.get("hashes_equal"),
            failed.get("wrote_new_receipt"),
            stale.get("ok"),
        )
    )
    print(
        "SUCCESS:TST-0159-probe1 both-states: completed retry suppressed, "
        "failed retry wrote"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
