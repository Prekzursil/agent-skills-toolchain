#!/usr/bin/env python3
"""Probe 2: growth control and independent recomputation from raw per-case results.

Catalog test: add 20 hard cases to a static system; naive aggregate drops;
intersection aggregate does not. Evidence: naive vs intersection with the
difference stated explicitly. Reviewer mandate: re-run from raw per-case
results and reproduce the reported effect.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.case_set import (  # noqa: E402
    HARD_N,
    compare_cross_version,
    load_case_set,
    load_ledger,
    results_for_run,
)

UID = "TST-0325"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0325.json"
CASES = REPO / "command-center" / "bench" / "cases"
LEDGER = REPO / "command-center" / "bench" / "results" / "TST-0325.jsonl"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def nearly(a: float, b: float, eps: float = 1e-12) -> bool:
    return abs(float(a) - float(b)) <= eps


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if f"SUCCESS:{UID}" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    v1 = load_case_set(CASES / "cs-v1.json")
    v2 = load_case_set(CASES / "cs-v2.json")
    rows = load_ledger(LEDGER)
    res1 = results_for_run(rows, "TST-0325-run-cs-v1")
    res2 = results_for_run(rows, "TST-0325-run-cs-v2")

    added = [c for c in v2["cases"] if c["id"] not in {x["id"] for x in v1["cases"]}]
    if len(added) != HARD_N:
        return fail(f"expected +{HARD_N} hard cases, got {len(added)}")
    if any(c.get("difficulty") != "hard" for c in added):
        return fail("added cases are not all hard")
    if any(res2[c["id"]] for c in added):
        return fail("static system passed a hard case")

    live = compare_cross_version(
        res1,
        v1["cases"],
        res2,
        v2["cases"],
        run_id_a="TST-0325-run-cs-v1",
        run_id_b="TST-0325-run-cs-v2",
        label_a="cs-v1",
        label_b="cs-v2",
    )
    naive_a = live["naive"]["a"]["pass_rate"]
    naive_b = live["naive"]["b"]["pass_rate"]
    inter_a = live["intersection"]["a"]["pass_rate"]
    inter_b = live["intersection"]["b"]["pass_rate"]
    if not (naive_b < naive_a):
        return fail(f"naive did not drop {naive_a} -> {naive_b}")
    if not nearly(inter_a, inter_b):
        return fail(f"intersection moved {inter_a} -> {inter_b}")
    if live["intersection"]["n"] != live["naive"]["a"]["n"]:
        return fail("intersection size != v1 n")
    if len(live["excluded"]["only_in_b"]) != HARD_N:
        return fail("excluded-from-intersection count != 20")

    expected_naive_b = live["naive"]["a"]["n_pass"] / (
        live["naive"]["a"]["n"] + HARD_N
    )
    if not nearly(naive_b, expected_naive_b):
        return fail("naive v2 is not n_pass/(n+20)")

    report = doc.get("report") or {}
    rec = report.get("cross_version_comparison") or {}
    rec_diff = rec.get("difference") or {}
    live_diff = live["difference"]
    for key in ("naive_delta", "intersection_delta", "composition_effect"):
        if key not in rec_diff:
            return fail(f"receipt difference missing {key}")
        if not nearly(rec_diff[key], live_diff[key]):
            return fail(f"receipt {key} {rec_diff[key]} != live {live_diff[key]}")
    if not rec_diff.get("statement"):
        return fail("difference statement absent")
    if "difference(naive-intersection)=" not in str(rec_diff["statement"]):
        return fail("difference statement does not name both numbers")

    if rec.get("status") != "COMPARED":
        return fail(f"receipt comparison status={rec.get('status')}")
    if not nearly(rec["naive"]["b"]["pass_rate"], naive_b):
        return fail("receipt naive v2 != live recompute")
    if not nearly(rec["intersection"]["delta"], 0.0):
        return fail("receipt intersection delta is not zero on a static system")

    # Independent arithmetic from integer counts (reviewer mandate).
    n1, p1 = live["naive"]["a"]["n"], live["naive"]["a"]["n_pass"]
    n2, p2 = live["naive"]["b"]["n"], live["naive"]["b"]["n_pass"]
    ni, pi_a = live["intersection"]["n"], live["intersection"]["a"]["n_pass"]
    pi_b = live["intersection"]["b"]["n_pass"]
    hand_naive = (p2 / n2) - (p1 / n1)
    hand_inter = (pi_b / ni) - (pi_a / ni)
    hand_comp = hand_naive - hand_inter
    if not nearly(hand_naive, live_diff["naive_delta"]):
        return fail("hand naive_delta mismatch")
    if not nearly(hand_inter, live_diff["intersection_delta"]):
        return fail("hand intersection_delta mismatch")
    if not nearly(hand_comp, live_diff["composition_effect"]):
        return fail("hand composition_effect mismatch")

    out = {
        "probe": "probe2-growth-control",
        "unit_id": UID,
        "pass": True,
        "hard_n_added": HARD_N,
        "naive_v1": naive_a,
        "naive_v2": naive_b,
        "naive_dropped": naive_b < naive_a,
        "intersection_v1": inter_a,
        "intersection_v2": inter_b,
        "intersection_unchanged": nearly(inter_a, inter_b),
        "naive_delta": live_diff["naive_delta"],
        "intersection_delta": live_diff["intersection_delta"],
        "composition_effect": live_diff["composition_effect"],
        "difference_statement": live_diff["statement"],
        "run_ids": ["TST-0325-run-cs-v1", "TST-0325-run-cs-v2"],
        "receipt_matches_live": True,
        "hand_recompute_matches": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(
        "SUCCESS:TST-0325-probe2 growth-control naive-drops "
        "intersection-holds difference-stated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
