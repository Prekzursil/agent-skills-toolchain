#!/usr/bin/env python3
"""Probe 2: detector stays silent on 20 control negatives; not vacuously silent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
from detector import fires  # noqa: E402
from load_run import best_silent, control_flag, gold_flag, live  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0141-probe2 {msg}")
    return 1


def meas(doc: dict, mid: str):
    for row in doc.get("measurements") or []:
        if row.get("id") == mid:
            return row.get("value")
    return None


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")

    corpus, assigned, ev = live()
    notes = {n["id"]: n for n in corpus["notes"]}
    best = best_silent(ev)
    combo = tuple(best.get("combo") or [])
    if not combo:
        return fail("no best combo")

    control_rows = [r for r in assigned["labels"] if control_flag(r)]
    if len(control_rows) < C.N_CONTROL_NEGATIVES:
        return fail(f"need {C.N_CONTROL_NEGATIVES} controls got {len(control_rows)}")
    for row in control_rows:
        if gold_flag(row):
            return fail(f"control {row['id']} is gold-positive")
        if fires(notes[row["id"]]["text"], combo):
            return fail(f"detector fired on control {row['id']}")

    gold_pos = [r for r in assigned["labels"] if gold_flag(r)]
    n_gold_fire = sum(1 for r in gold_pos if fires(notes[r["id"]]["text"], combo))
    if n_gold_fire < 1:
        return fail("detector silent on all gold positives (vacuous silence)")

    live_fp = int(best.get("control_fp") or best.get("control_fp") or 0)
    if live_fp != 0:
        return fail(f"evaluate control_fp={live_fp}")
    count = meas(doc, "control-false-positive-count")
    if count is None or int(count) != 0:
        return fail("artifact control-false-positive-count is not 0")
    rate = meas(doc, "control-false-positive-rate")
    if rate is None or abs(float(rate)) > 1e-12:
        return fail(f"artifact control-false-positive-rate is not 0 ({rate!r})")
    rec = doc.get("detector_control") or {}
    if rec.get("silent") is not True:
        return fail("artifact detector_control.silent is not true")
    if rec.get("fires_on_at_least_one_gold_positive") is not True:
        return fail("artifact did not record both-states gold fire")
    if rec.get("both_states") is not True:
        return fail("artifact both_states is not true")

    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        return fail("reviewer record missing")

    print(
        f"controls={len(control_rows)} silent=True control_fp=0 "
        f"gold_pos={len(gold_pos)} gold_fires={n_gold_fire} combo={list(combo)}"
    )
    print("reviewer_id=" + str(rev.get("reviewer_id")))
    print("SUCCESS:RES-0141-probe2 negative-control silence both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
