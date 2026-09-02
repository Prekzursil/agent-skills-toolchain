#!/usr/bin/env python3
"""Probe 1: early-round citation rate, retrieval on and off, same council.

Live re-run of tools/council/evidence/retrieve.py. Receipt numbers must match
the live rates; a retrieval log must name the anchors fetched per late turn.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.evidence.retrieve import (  # noqa: E402
    build_overflow_council,
    run_both_configurations,
)

ART = REPO / "command-center/receipts/IMP-0349.json"
LOG = HERE / "retrieval-log.json"
FIX = HERE / "fixtures" / "overflow_council.json"
MODULE = REPO / "tools/council/evidence/retrieve.py"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0349-probe1 {msg}")
    return 1


def main() -> int:
    if not MODULE.is_file():
        return fail("retrieve.py missing")
    live = run_both_configurations(build_overflow_council(), token_budget=48)
    printable = {
        k: live[k]
        for k in (
            "council_id",
            "same_council",
            "token_budget",
            "early_anchor_ids",
            "overflow_late_on",
            "overflow_late_off",
            "rate_on",
            "rate_off",
            "late_fetches_on",
            "pass_experiment",
            "pass_negative_control",
        )
    }
    print(json.dumps(printable, sort_keys=True, default=str)[:4000])

    if not live.get("same_council"):
        return fail("on/off used different councils")
    if not live.get("overflow_late_off") or not live.get("overflow_late_on"):
        return fail("late turns did not overflow")
    if not live.get("pass_experiment"):
        return fail("experiment predicate false")
    rate_on = float(live["rate_on"]["rate"])
    rate_off = float(live["rate_off"]["rate"])
    if rate_on != 1.0:
        return fail(f"rate_on={rate_on} want=1.0")
    if rate_off != 0.0:
        return fail(f"rate_off={rate_off} want=0.0")
    fetches = live["late_fetches_on"]
    if len(fetches) != 2:
        return fail(f"late_fetches={len(fetches)} want=2")
    if fetches[0]["fetched_anchor_ids"] != ["E-ALPHA"]:
        return fail(f"turn7 fetch {fetches[0]['fetched_anchor_ids']}")
    if fetches[1]["fetched_anchor_ids"] != ["E-DELTA"]:
        return fail(f"turn8 fetch {fetches[1]['fetched_anchor_ids']}")
    if fetches[0]["turn"] != 7 or fetches[1]["turn"] != 8:
        return fail("late fetch turns are not 7 then 8")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("receipt not an object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:IMP-0349" not in text:
        return fail("sentinel-absent")
    for key in (
        "unit_id",
        "artifact_paths",
        "spec_anchor",
        "evidence",
        "test_ids",
        "negative_control_ids",
        "reviewer_verdict",
        "residual_unknowns",
    ):
        if key not in doc:
            return fail(f"receipt missing {key}")
    if doc.get("unit_id") != "IMP-0349":
        return fail(f"unit_id {doc.get('unit_id')}")
    if not isinstance(doc.get("artifact_paths"), list) or not doc["artifact_paths"]:
        return fail("artifact_paths empty")
    exp = doc.get("experiment") or {}
    if float(exp.get("rate_on")) != rate_on:
        return fail("receipt rate_on != live")
    if float(exp.get("rate_off")) != rate_off:
        return fail("receipt rate_off != live")
    if list(exp.get("late_fetched_anchor_ids") or []) != [
        fetches[0]["fetched_anchor_ids"],
        fetches[1]["fetched_anchor_ids"],
    ]:
        return fail("receipt late fetches != live")

    if not LOG.is_file():
        return fail("retrieval-log.json missing")
    log_doc = json.loads(LOG.read_text(encoding="utf-8"))
    per_turn = log_doc.get("per_turn") or []
    if not per_turn:
        return fail("retrieval log empty")
    late_log = [e for e in per_turn if int(e.get("turn") or 0) >= 7]
    if [e.get("fetched_anchor_ids") for e in late_log] != [
        ["E-ALPHA"],
        ["E-DELTA"],
    ]:
        return fail("retrieval log late fetches != live")
    if not FIX.is_file():
        return fail("overflow fixture missing")

    print(
        f"rate_on={rate_on} rate_off={rate_off} "
        f"late_fetches={ [e['fetched_anchor_ids'] for e in fetches] }"
    )
    print("SUCCESS:IMP-0349-probe1 citation-rate both-configs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
