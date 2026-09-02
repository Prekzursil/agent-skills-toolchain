#!/usr/bin/env python3
"""Named probe 2: estate empty-input seeds + control timing separation.

Signal (a): every result row records input_bytes and input_items.
Signal (b): the non-zero control's median elapsed_ns is above the empty
path by MIN_TIMING_DELTA_NS.

Regression seeds: two estate benches that scored EMPTY input as a clean
green (naive_score). Live gate must FLAG both. A silent mutant that
keeps scoring them is the detector control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.nonempty import (  # noqa: E402
    CONTROL_BYTES,
    ESTATE_SEED_IDS,
    MIN_TIMING_DELTA_NS,
    STATUS_FLAGGED,
    STATUS_SCORED,
    control_case,
    estate_seed_router_empty,
    estate_seed_suite_empty,
    load_case,
    mutant_score_empty,
    naive_score,
    payload_bytes,
    result_schema_errors,
    run_case,
    run_suite,
    timing_separation,
)

UNIT = "TST-0230"
RAW = HERE / "probe2-seeds-and-timing.raw.json"
FIXTURES = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def as_case(path: Path) -> dict:
    doc = load_case(path)
    doc["payload"] = payload_bytes(doc)
    return doc


def main() -> int:
    router = as_case(FIXTURES / "seed-router-empty.json")
    suite = as_case(FIXTURES / "seed-suite-empty.json")
    if router["id"] != ESTATE_SEED_IDS[0] or suite["id"] != ESTATE_SEED_IDS[1]:
        return fail("fixture ids do not match ESTATE_SEED_IDS")

    naive_router = naive_score(router)
    naive_suite = naive_score(suite)
    if naive_router.get("status") != STATUS_SCORED or "score" not in naive_router:
        return fail("naive router seed was not a scored green")
    if naive_suite.get("status") != STATUS_SCORED or "score" not in naive_suite:
        return fail("naive suite seed was not a scored green")
    if naive_router.get("score") != 0 or naive_suite.get("score") != 0:
        return fail("naive empty seeds did not emit the historical score=0 green")

    live_router = run_case(router)
    live_suite = run_case(suite)
    for name, row in (("router", live_router), ("suite", live_suite)):
        if row.get("status") != STATUS_FLAGGED:
            return fail(f"live {name} seed status={row.get('status')} not FLAGGED")
        if "score" in row:
            return fail(f"live {name} seed carried a score")
        errs = result_schema_errors(row)
        if errs:
            return fail(f"live {name} schema {errs}")
        if int(row["input_bytes"]) != 0 or int(row["input_items"]) != 0:
            return fail(f"live {name} did not record zero input size")

    helpers = run_suite([estate_seed_router_empty(), estate_seed_suite_empty()])
    if helpers["flagged_n"] != 2 or helpers["scored_n"] != 0:
        return fail(f"helper seeds not both flagged: {helpers}")
    if set(helpers["flagged_ids"]) != set(ESTATE_SEED_IDS):
        return fail(f"flagged ids {helpers['flagged_ids']}")

    m_router = mutant_score_empty(router)
    m_suite = mutant_score_empty(suite)
    if m_router.get("status") != STATUS_SCORED or m_suite.get("status") != STATUS_SCORED:
        return fail("mutant did not keep scoring the estate seeds")
    if live_router["status"] == m_router["status"]:
        return fail("live and mutant agreed on router seed")

    control = control_case()
    live_ctrl = run_case(control)
    if live_ctrl.get("status") != STATUS_SCORED:
        return fail("control case was not scored")
    if int(live_ctrl["input_bytes"]) != CONTROL_BYTES:
        return fail(f"control input_bytes={live_ctrl['input_bytes']}")
    if int(live_ctrl["input_items"]) != CONTROL_BYTES:
        return fail(f"control input_items={live_ctrl['input_items']}")
    if not isinstance(live_ctrl.get("elapsed_ns"), int) or live_ctrl["elapsed_ns"] <= 0:
        return fail("control elapsed_ns missing")
    ctrl_errs = result_schema_errors(live_ctrl)
    if ctrl_errs:
        return fail(f"control schema {ctrl_errs}")

    timing = timing_separation()
    if not timing.get("separated"):
        return fail(
            "control timing not above empty/noise: "
            f"empty_med={timing.get('empty_median_ns')} "
            f"control_med={timing.get('control_median_ns')} "
            f"delta={timing.get('delta_ns')} "
            f"min={MIN_TIMING_DELTA_NS}"
        )
    if int(timing["work_units_control"]) <= int(timing["work_units_empty"]):
        return fail("control work_units not greater than empty")
    if int(timing["empty_bytes"]) != 0:
        return fail("timing empty_bytes was not 0")
    if int(timing["control_bytes"]) != CONTROL_BYTES:
        return fail("timing control_bytes mismatch")

    mixed = run_suite([router, suite, control])
    if not mixed.get("all_counts_recorded"):
        return fail("suite did not record per-case input counts")
    if mixed["flagged_n"] != 2 or mixed["scored_n"] != 1:
        return fail(f"mixed suite flagged/scored {mixed['flagged_n']}/{mixed['scored_n']}")

    payload = {
        "pass": True,
        "probe": "probe2-seeds-and-timing",
        "unit_id": UNIT,
        "signal_a_per_case_counts": True,
        "signal_b_timing_separation": True,
        "estate_seeds": {
            "ids": list(ESTATE_SEED_IDS),
            "naive_router": {
                "status": naive_router["status"],
                "score": naive_router["score"],
                "input_bytes": naive_router["input_bytes"],
            },
            "naive_suite": {
                "status": naive_suite["status"],
                "score": naive_suite["score"],
                "input_bytes": naive_suite["input_bytes"],
            },
            "live_router": {
                "status": live_router["status"],
                "reason_id": live_router["reason_id"],
                "input_bytes": live_router["input_bytes"],
                "input_items": live_router["input_items"],
                "score_present": "score" in live_router,
            },
            "live_suite": {
                "status": live_suite["status"],
                "reason_id": live_suite["reason_id"],
                "input_bytes": live_suite["input_bytes"],
                "input_items": live_suite["input_items"],
                "score_present": "score" in live_suite,
            },
        },
        "timing": {
            "empty_median_ns": timing["empty_median_ns"],
            "control_median_ns": timing["control_median_ns"],
            "delta_ns": timing["delta_ns"],
            "min_delta_ns": timing["min_delta_ns"],
            "separated": timing["separated"],
            "control_bytes": timing["control_bytes"],
            "work_units_control": timing["work_units_control"],
            "work_units_empty": timing["work_units_empty"],
        },
        "mutant_keeps_scoring_seeds": True,
        "live_disagrees_with_mutant": True,
        "control_input_bytes": live_ctrl["input_bytes"],
        "control_elapsed_ns": live_ctrl["elapsed_ns"],
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        f"seeds_flagged=2 naive_green=True delta_ns={timing['delta_ns']} "
        f"separated={timing['separated']}"
    )
    print("SUCCESS:TST-0230-probe2 estate seeds FLAGGED; control timing above noise")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
