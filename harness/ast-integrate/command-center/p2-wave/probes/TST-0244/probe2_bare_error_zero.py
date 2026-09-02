#!/usr/bin/env python3
"""Probe 2: a deliberately bare error scores zero; catalog messages still score 3."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from gates.failure_taxonomy import measure_negative_control  # noqa: E402

UNIT = "TST-0244"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0244.json"
SENTINEL = "SUCCESS:TST-0244"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def receipt_ok() -> bool | None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return None
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    neg = doc.get("negative_control") or {}
    if state in NOT_DELIVERING:
        return False
    if SENTINEL not in text:
        return False
    # 0 is a valid score; do not coerce it with `or`.
    if "bare_score" not in neg or int(neg["bare_score"]) != 0:
        return False
    if int(neg.get("catalog_score") if neg.get("catalog_score") is not None else 0) != 3:
        return False
    return True


def main() -> int:
    live = measure_negative_control()
    rec = receipt_ok()
    ok = bool(live.get("pass")) and rec is not False
    payload = {
        "probe": "probe2-bare-error-zero",
        "unit_id": UNIT,
        "pass": ok,
        "method": "rubric-on-captured-text",
        "data_field": "rubric.score",
        "measurement_kind": "bare-error-scores-zero-both-states",
        "bare_score": live["score_bare"]["score"],
        "shrug_score": live["score_shrug"]["score"],
        "catalog_score": live["score_catalog"]["score"],
        "naive_bare_score": live["naive_bare_score"],
        "detector_is_not_constant": live["detector_is_not_constant"],
        "both_states": live["both_states"],
        "bare_excerpt": (live["bare_traceback"] or "")[:240],
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": rec,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if live["score_bare"]["score"] != 0:
        return fail(f"bare_score={live['score_bare']['score']}")
    if live["score_shrug"]["score"] != 0:
        return fail(f"shrug_score={live['score_shrug']['score']}")
    if live["score_catalog"]["score"] != 3:
        return fail("catalog timeout message did not score 3")
    if not live["detector_is_not_constant"]:
        return fail("rubric is a constant (agrees with naive-always-3)")
    if not live["both_states"]:
        return fail("both-states failed")
    if rec is False:
        return fail("receipt does not match live negative control")
    print(
        f"bare={live['score_bare']['score']} shrug={live['score_shrug']['score']} "
        f"catalog={live['score_catalog']['score']} naive={live['naive_bare_score']}"
    )
    print(f"SUCCESS:{UNIT}-probe2 bare error scores zero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
