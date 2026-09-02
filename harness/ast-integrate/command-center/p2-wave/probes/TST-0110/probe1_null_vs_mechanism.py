#!/usr/bin/env python3
"""Probe 1: empty-input control, then null vs mechanism both-states per benchmark.

Order is load-bearing: empty input is failed before any number is trusted.
A metric that moves on the null is GAMEABLE and must be named.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402
import harness as H  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / "command-center/receipts/TST-0110.json"
SCHEMA = REPO / "command-center/schema/benchmark-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0110/probe1_null_vs_mechanism.py"
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0110-probe1 {msg}")
    return 1


def main() -> int:
    live = D.measure_all()
    print(f"seed={live['seed']} n_runs={live['n_runs']}")
    print(f"empty_input_control={json.dumps(live['empty_input_control'], sort_keys=True)}")
    if not live["empty_input_ok"]:
        return fail("empty-input control did not fire on every benchmark")
    print("empty_input_run_is_failed_not_reported=True")

    for row in live["rows"]:
        ns = row["null_change_sample"]
        ms = row["mechanism_change_sample"]
        vb = row["variance_band"]
        print(
            f"bench={row['name']} n_inputs={row['n_inputs']} metric={row['metric_id']} "
            f"baseline_mean={vb['mean']} std={vb['std']} mde={vb['mde']} "
            f"null_delta={ns['delta']} null_sig={ns['significant']} "
            f"mech_delta={ms['delta']} mech_sig={ms['significant']} "
            f"verdict={row['verdict']} expected={row['expected']}"
        )
        if row["n_inputs"] < 1:
            return fail(f"{row['name']} emitted a number on empty input")
        if row["verdict"] != row["expected"]:
            return fail(
                f"{row['name']} verdict={row['verdict']} expected={row['expected']}"
            )

    honest = [r for r in live["rows"] if r["expected"] == "HONEST"]
    planted = [r for r in live["rows"] if r["planted"]]
    if len(honest) < 4:
        return fail(f"honest benches={len(honest)} want>=4")
    if not planted:
        return fail("planted GAMEABLE benchmark missing")
    for r in honest:
        if r["null_change_sample"]["significant"]:
            return fail(f"honest {r['name']} moved on null")
        if not r["mechanism_change_sample"]["significant"]:
            return fail(f"honest {r['name']} did not move on mechanism")
    for r in planted:
        if r["verdict"] != "GAMEABLE" or not r["null_change_sample"]["significant"]:
            return fail(f"planted {r['name']} was not GAMEABLE on null")
        print(f"GAMEABLE {r['name']} (must replace; {r.get('replace_with')})")

    if not live["expected_ok"]:
        return fail("expected_ok=false")
    if "workflow_stage_count" not in live["gameable_named"]:
        return fail("workflow_stage_count not named GAMEABLE")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0110" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    pay = D.receipt_payload(doc)
    if pay.get("seed") != H.SEED:
        return fail(f"seed mismatch {pay.get('seed')}")
    named = list(pay.get("gameable_named") or [])
    if "workflow_stage_count" not in named:
        return fail("receipt did not name workflow_stage_count GAMEABLE")
    by_name = {b["name"]: b for b in pay.get("benchmarks") or []}
    for r in live["rows"]:
        b = by_name.get(r["name"])
        if not b:
            return fail(f"receipt missing {r['name']}")
        if b.get("n_inputs") != r["n_inputs"]:
            return fail(f"{r['name']} n_inputs receipt={b.get('n_inputs')} live={r['n_inputs']}")
        if b.get("verdict") != r["verdict"]:
            return fail(f"{r['name']} verdict receipt={b.get('verdict')} live={r['verdict']}")
        if list(b["null_change"]["raw"]) != list(r["null_change_sample"]["raw"]):
            return fail(f"{r['name']} null raw mismatch")
        if list(b["mechanism_change"]["raw"]) != list(r["mechanism_change_sample"]["raw"]):
            return fail(f"{r['name']} mechanism raw mismatch")

    if not SL.rejects_garbage():
        return fail("schema accepted garbage")
    errs = SL.error_messages(doc)
    if errs:
        return fail(f"schema {errs[0]}")
    print("schema_valid=True")
    print("test_null_change_does_not_move_the_metric=PASS")
    print("test_mechanism_change_does_move_the_metric=PASS")
    print("SUCCESS:TST-0110-probe1 empty-input both-states GAMEABLE-named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
