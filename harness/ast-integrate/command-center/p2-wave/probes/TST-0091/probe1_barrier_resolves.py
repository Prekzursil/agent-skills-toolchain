#!/usr/bin/env python3
"""Probe 1: both-states barrier — naive parallel() blocks; per-unit pipeline resolves."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0091.json"
UNIT = "TST-0091"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0091" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")

    barrier = S.test_barrier_resolves_despite_one_hung_unit()
    both = barrier["both_states"]
    payload = {
        "probe": "probe1-barrier-resolves",
        "unit_id": UNIT,
        "pass": barrier["pass"],
        "n": barrier["n"],
        "hung_id": barrier["hung_id"],
        "naive_blocks": both["naive_blocks"],
        "fixed_resolves": both["fixed_resolves"],
        "naive_zero_durable": both["naive_zero_durable"],
        "naive_n_durable": barrier["naive"]["n_durable"],
        "fixed_n_success": barrier["fixed"]["n_success"],
        "fixed_n_timeout": barrier["fixed"]["n_timeout"],
        "fixed_wall_s": barrier["fixed"]["wall_s"],
        "both_states": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"naive_resolved={barrier['naive']['resolved']} "
        f"naive_durable={barrier['naive']['n_durable']} "
        f"fixed_resolved={barrier['fixed']['resolved']} "
        f"n_success={barrier['fixed']['n_success']} "
        f"n_timeout={barrier['fixed']['n_timeout']} "
        f"wall_s={barrier['fixed']['wall_s']:.4f}"
    )
    if not barrier["pass"]:
        return fail("live both-states barrier did not pass")
    if not (both["naive_blocks"] and both["fixed_resolves"] and both["naive_zero_durable"]):
        return fail("both-states incomplete")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    named = tests.get("test_barrier_resolves_despite_one_hung_unit")
    if not named or named.get("result") != "PASS":
        return fail("receipt missing PASS for test_barrier_resolves_despite_one_hung_unit")
    cohort = doc.get("cohort") or {}
    if cohort.get("n") != S.N or cohort.get("n_success") != S.N - 1:
        return fail("receipt cohort drift vs live N")
    if cohort.get("barrier_resolved") is not True:
        return fail("receipt cohort not resolved")
    both_doc = doc.get("both_states") or {}
    if both_doc.get("naive_blocks") is not True or both_doc.get("fixed_resolves") is not True:
        return fail("receipt both_states drift")

    print("SUCCESS:TST-0091-probe1 barrier resolves despite one hung unit (both-states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
