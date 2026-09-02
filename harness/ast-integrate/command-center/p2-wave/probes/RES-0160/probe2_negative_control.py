#!/usr/bin/env python3
"""Probe 2: negative control — WOULD-NOT-HAVE-PASSED on a mechanism still in use.

A gate that retroactively blesses everything already adopted is not a gate.
Defaults to REFUTED unless the control fires.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import gate as G  # noqa: E402
import inventory as I  # noqa: E402

ART = REPO / (
    "command-center/research/gem-hunt/"
    "RES-0160-gem-adoption-gate-with-measured-improvement.json"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    # Default to REFUTED: every failure path prints REFUTED.
    live = I.run_backtest()
    pop = live["population"]
    records = live["records"]

    still_failed = [
        r
        for r in pop["rows"]
        if r["backtest_verdict"] == "WOULD-NOT-HAVE-PASSED" and r["still_in_use"]
    ]
    if not still_failed:
        print("REFUTED:RES-0160-probe2 no WOULD-NOT-HAVE-PASSED still in use")
        return 1

    if pop["blesses_everything"]:
        print("REFUTED:RES-0160-probe2 historical population blesses everything")
        return 1

    mutant_pop = G.evaluate_population(G.blessing_mutant(records))
    if not mutant_pop["blesses_everything"]:
        print("REFUTED:RES-0160-probe2 blessing mutant did not bless everything")
        return 1
    if mutant_pop["negative_control_fired"]:
        print("REFUTED:RES-0160-probe2 blessing mutant still looks like a gate")
        return 1

    plant = G.evaluate_record(
        {"mechanism_id": "plant-no-metric-still-in-use", "still_in_use": True}
    )
    if plant["backtest_verdict"] != "WOULD-NOT-HAVE-PASSED":
        print("REFUTED:RES-0160-probe2 no-metric plant was not WOULD-NOT-HAVE-PASSED")
        return 1

    if not ART.is_file():
        print("REFUTED:RES-0160-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"REFUTED:RES-0160-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:RES-0160" not in text:
        print("REFUTED:RES-0160-probe2 sentinel-absent")
        return 1
    if "WOULD-NOT-HAVE-PASSED" not in text:
        print("REFUTED:RES-0160-probe2 artifact omits WOULD-NOT-HAVE-PASSED")
        return 1
    bt = doc.get("back_test") or {}
    if bt.get("negative_control_fired") is not True:
        print("REFUTED:RES-0160-probe2 artifact negative_control_fired is not true")
        return 1
    if int(bt.get("would_not_have_passed_still_in_use") or 0) < 1:
        print("REFUTED:RES-0160-probe2 artifact still-in-use fail count < 1")
        return 1
    art_ids = set(bt.get("still_in_use_would_not_have_passed") or [])
    live_ids = {r["mechanism_id"] for r in still_failed}
    if art_ids != live_ids:
        print(f"REFUTED:RES-0160-probe2 still-in-use ids art={art_ids} live={live_ids}")
        return 1

    keyed = live["live"]["pre_r3_keyed_garbage_accepted"]
    r3 = live["live"]["schema_doc_verdict_keyed"]
    if keyed is not True:
        print("REFUTED:RES-0160-probe2 R2 instrument no longer accepts keyed garbage")
        return 1
    if r3.get("ok") is not False:
        print("REFUTED:RES-0160-probe2 R3 merit stage accepted keyed garbage")
        return 1

    print(
        f"still_in_use_WOULD-NOT-HAVE-PASSED={sorted(live_ids)} "
        f"blessing_mutant_blesses={mutant_pop['blesses_everything']} "
        f"no_metric_plant={plant['backtest_verdict']} "
        f"r2_keyed_accept={keyed} r3_stage={r3.get('stage')}"
    )
    print("SUCCESS:RES-0160-probe2 negative control fired on still-in-use mechanism")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
