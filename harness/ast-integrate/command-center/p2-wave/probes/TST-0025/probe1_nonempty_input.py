#!/usr/bin/env python3
"""Probe 1: empty inputs FAIL (no time); every number carries n_inputs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.OUT_REL
SCHEMA = REPO / H.SCHEMA_REL
UNIT = H.UNIT


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    from router.shadow import load_catalog  # noqa: WPS433 — path set by harness

    catalog = load_catalog()
    policy = H.make_policy()
    empty_router = H.empty_control(
        "router_latency", lambda: H.run_router([], catalog)
    )
    empty_hook = H.empty_control(
        "hook_overhead", lambda: H.run_hooks([], policy)
    )
    print(
        json.dumps(
            {"empty_router": empty_router, "empty_hook": empty_hook},
            sort_keys=True,
        )
    )
    if not empty_router["failed"] or empty_router["reported_time"] is not None:
        return fail(f"empty router did not FAIL: {empty_router}")
    if not empty_hook["failed"] or empty_hook["reported_time"] is not None:
        return fail(f"empty hook did not FAIL: {empty_hook}")

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if H.COMPLETION_SENTINEL not in text:
        return fail("completion_sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")

    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        return fail("catalog output_schema missing")
    shim = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if not str(shim.get("$ref") or "").endswith("#/$defs/benchmark-receipt"):
        return fail("catalog shim does not pin benchmark-receipt")

    garbage = [{}, {"totally": "unrelated"}, {"x": "x" * 200}]
    rejected = 0
    for g in garbage:
        if H.schema_errors(g):
            rejected += 1
    if rejected != 3:
        return fail(f"schema accepted garbage rejected={rejected}/3")
    errs = H.schema_errors(doc)
    if errs:
        return fail(f"schema {errs[0]}")

    view = H.payload(doc)
    if (view.get("kind") or (doc.get("report") or {}).get("kind")) != "benchmark-receipt":
        return fail(f"report.kind={view.get('kind')}")

    controls = view.get("empty_input_controls") or []
    if len(controls) < 2:
        return fail("need two empty-input controls")
    for row in controls:
        if row.get("n_inputs") != 0 or row.get("failed") is not True:
            return fail(f"empty control not a failure: {row}")
        if row.get("reported_time") is not None:
            return fail(f"empty control reported a time: {row}")

    benches = view.get("benchmarks") or []
    if len(benches) < 4:
        return fail(f"benchmarks={len(benches)}")
    for b in benches:
        n_in = int(b.get("n_inputs") or 0)
        if n_in < 1:
            return fail(f"{b.get('id')} n_inputs={n_in}")
        arms = b.get("arms") or []
        if not arms:
            return fail(f"{b.get('id')} missing required arms[]")
        arm0 = arms[0]
        if not isinstance(arm0, dict) or not arm0.get("id"):
            return fail(f"{b.get('id')} arms[0] missing id")
        arm_raw = arm0.get("raw_ns") or []
        if len(arm_raw) < 11:
            return fail(f"{b.get('id')} arms[0].raw_ns n={len(arm_raw)}")
        printed = b.get("printed") or []
        if len(printed) < 4:
            return fail(f"{b.get('id')} printed lines missing")
        token = f"n_inputs={n_in}"
        for line in printed:
            if token not in line:
                return fail(f"{b.get('id')} printed line missing cardinality: {line}")
        stats = b.get("statistics") or {}
        for key in ("median_ns", "mean_ns", "iqr_ns", "ci95_lo_ns", "ci95_hi_ns"):
            if key not in stats:
                return fail(f"{b.get('id')} missing {key}")
        print(
            f"{b['id']} value={b.get('value')} {b.get('unit')} "
            f"median_ns={stats['median_ns']} n_inputs={n_in}"
        )

    named = view.get("named_benchmarks") or {}
    for key in (
        "router_latency",
        "hook_overhead",
        "fanout_throughput",
        "suite_wall_clock",
    ):
        if key not in named:
            return fail(f"named_benchmarks missing {key}")

    print(
        "empty_failed=True reported_time=null n_inputs_on_every_number=True "
        f"schema_garbage_rejected={rejected}/3"
    )
    print(
        "SUCCESS:TST-0025-probe1 empty input FAILED not timed; "
        "cardinality printed beside every number"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
