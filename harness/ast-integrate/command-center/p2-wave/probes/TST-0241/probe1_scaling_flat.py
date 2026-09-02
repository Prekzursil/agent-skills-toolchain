#!/usr/bin/env python3
"""Probe 1: empty inputs FAIL; scaling 16..2048 is flat; append bytes are O(1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"FAILED:TST-0241-probe1 jsonschema missing: {exc}") from exc

ART = H.REPO / H.OUT_REL
UNIT = H.UNIT
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    (HERE / "_work").mkdir(parents=True, exist_ok=True)
    empty_dispatch = H.empty_control(
        "dispatch_cohort",
        lambda: H.dispatch_cohort([], H.AppendLedger(HERE / "_work" / "p1-empty-d.jsonl")),
    )
    empty_append = H.empty_control(
        "append_ledger",
        lambda: H.AppendLedger(HERE / "_work" / "p1-empty-a.jsonl").write_all([]),
    )
    print(json.dumps({"empty_dispatch": empty_dispatch, "empty_append": empty_append}, sort_keys=True))
    if not empty_dispatch["failed"] or empty_dispatch["reported_time"] is not None:
        return fail(f"empty dispatch did not FAIL: {empty_dispatch}")
    if not empty_append["failed"] or empty_append["reported_time"] is not None:
        return fail(f"empty append did not FAIL: {empty_append}")

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if H.COMPLETION_SENTINEL not in text:
        return fail("completion_sentinel absent")
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")

    schema = json.loads((H.REPO / H.BENCH_SCHEMA_REL).read_text(encoding="utf-8"))
    garbage = [{}, {"totally": "unrelated"}, {"x": "x" * 200}]
    rejected = 0
    for g in garbage:
        try:
            jsonschema.Draft7Validator(schema).validate(g)
        except jsonschema.ValidationError:
            rejected += 1
    if rejected != 3:
        return fail(f"schema accepted garbage rejected={rejected}/3")
    errs = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        return fail(f"schema {errs[0].message} path={list(errs[0].path)}")

    frag_root = json.loads((H.REPO / H.SCHEMA_REL).read_text(encoding="utf-8"))
    frag = (frag_root.get("$defs") or {}).get("benchmark_result")
    if not isinstance(frag, dict):
        return fail("$defs.benchmark_result missing")
    ferrs = sorted(jsonschema.Draft7Validator(frag).iter_errors(doc), key=lambda e: list(e.path))
    if ferrs:
        return fail(f"fragment {ferrs[0].message} path={list(ferrs[0].path)}")

    controls = doc.get("empty_input_controls") or []
    if len(controls) < 2:
        return fail("need two empty-input controls")
    for row in controls:
        if row.get("n_inputs") != 0 or row.get("failed") is not True:
            return fail(f"empty control not a failure: {row}")
        if row.get("reported_time") is not None:
            return fail(f"empty control reported a time: {row}")

    scaling = doc.get("scaling") or {}
    sizes = list(scaling.get("sizes") or [])
    if sizes != list(H.SIZES):
        return fail(f"sizes={sizes} want={list(H.SIZES)}")

    append_curve = scaling.get("append_curve") or []
    if [r.get("n") for r in append_curve] != list(H.SIZES):
        return fail("append_curve missing a required size")
    a16 = next(r for r in append_curve if r["n"] == 16)
    a2048 = next(r for r in append_curve if r["n"] == 2048)
    append_ratio = a2048["bytes_this_write"] / max(a16["bytes_this_write"], 1)
    if append_ratio >= 2.0:
        return fail(f"append write-size grew: ratio={append_ratio}")

    clf = scaling.get("classification") or {}
    verdicts = clf.get("verdicts") or clf
    if verdicts.get("dispatch_per_unit_flat") is not True:
        return fail(f"dispatch not flat: {clf}")
    if verdicts.get("append_write_o1") is not True:
        return fail(f"append writes not O(1): {clf}")
    if not H.production_bytes_are_o1(scaling.get("production_foundry") or []):
        return fail("foundry production writes are not O(1)")
    if not H.production_bytes_are_o1(scaling.get("production_close") or []):
        return fail("close.append_event writes are not O(1)")

    benches = {b["id"]: b for b in (doc.get("benchmarks") or [])}
    for bid in ("dispatch_per_unit", "append_write", "rewrite_write", "suite_wall_clock"):
        if bid not in benches:
            return fail(f"missing benchmark {bid}")
        for arm in benches[bid]["arms"]:
            n_in = int(arm.get("n_inputs") or 0)
            if n_in < 1:
                return fail(f"{bid}/{arm.get('id')} n_inputs={n_in}")
            printed = arm.get("printed") or []
            if len(printed) < 4:
                return fail(f"{bid}/{arm.get('id')} printed lines missing")
            token = f"n_inputs={n_in}"
            for line in printed:
                if token not in line:
                    return fail(f"printed line missing cardinality: {line}")
            raw = arm.get("raw_ns") or []
            if len(raw) < 11:
                return fail(f"{bid}/{arm.get('id')} raw_ns n={len(raw)}")
            stats = arm.get("statistics") or {}
            for key in ("median_ns", "mean_ns", "iqr_ns", "ci95_lo_ns", "ci95_hi_ns"):
                if key not in stats:
                    return fail(f"{bid}/{arm.get('id')} missing {key}")

    named = doc.get("named_benchmarks") or {}
    for key in ("router_latency", "hook_overhead", "fanout_throughput", "suite_wall_clock"):
        if key not in named:
            return fail(f"named_benchmarks missing {key}")

    payload = {
        "probe": "probe1-scaling-flat",
        "unit_id": UNIT,
        "append_write_ratio_2048_over_16": append_ratio,
        "per_unit_ratio_2048_over_256": clf.get("per_unit_ratio_2048_over_256"),
        "schema_garbage_rejected": rejected,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:TST-0241-probe1 empty FAIL; append bytes O(1); "
        "per-unit dispatch flat across 16..2048"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
