#!/usr/bin/env python3
"""Probe 1: independently reproduce the measured gain and both-states on the new case.

Mechanically different from probe 2: this probe execs join_url from source strings
in-process and scores the measurement pack. It does not mutate files, does not
delete cases, and does not apply a revert.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _common import (  # noqa: E402
    BASELINE_NEW_GOT,
    BASELINE_SRC,
    CASE_ID,
    IMPROVED_NEW_GOT,
    IMPROVED_SRC,
    MEASURE_CASES,
    NEW_CASE,
    ORIGINAL_CASES,
)

ART = Path(__file__).resolve().parents[3] / "receipts" / "CNF-0181.json"


def _load(src: str):
    ns: dict = {}
    exec(src, ns)  # noqa: S102
    return ns["join_url"]


def _run(fn, cases):
    rows = []
    ok = 0
    for c in cases:
        got = fn(c["base"], c["path"])
        passed = got == c["want"]
        ok += int(passed)
        rows.append({"id": c["id"], "got": got, "want": c["want"], "pass": passed})
    return ok, rows


def main() -> int:
    base_fn = _load(BASELINE_SRC)
    imp_fn = _load(IMPROVED_SRC)

    base_ok, base_rows = _run(base_fn, MEASURE_CASES)
    imp_ok, imp_rows = _run(imp_fn, MEASURE_CASES)

    new_base = next(r for r in base_rows if r["id"] == CASE_ID)
    new_imp = next(r for r in imp_rows if r["id"] == CASE_ID)
    orig_base_ok, _ = _run(base_fn, ORIGINAL_CASES)
    orig_imp_ok, _ = _run(imp_fn, ORIGINAL_CASES)

    gain = imp_ok > base_ok
    both_states = (not new_base["pass"]) and new_imp["pass"]
    orig_invisible = orig_base_ok == len(ORIGINAL_CASES) == orig_imp_ok
    got_ok = (
        new_base["got"] == BASELINE_NEW_GOT and new_imp["got"] == IMPROVED_NEW_GOT
    )

    payload = {
        "probe": "probe1-gain-both-states",
        "unit_id": "CNF-0181",
        "case_id": CASE_ID,
        "baseline_ok": base_ok,
        "improved_ok": imp_ok,
        "n": len(MEASURE_CASES),
        "gain": gain,
        "both_states": both_states,
        "original_suite_green_on_both_trees": orig_invisible,
        "new_case": {
            "baseline_got": new_base["got"],
            "improved_got": new_imp["got"],
            "baseline_pass": new_base["pass"],
            "improved_pass": new_imp["pass"],
        },
        "pass": bool(gain and both_states and orig_invisible and got_ok),
    }
    print(json.dumps(payload, sort_keys=True))

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:CNF-0181" not in text:
            print("FAILED:CNF-0181-probe1 receipt missing sentinel")
            return 1
        if CASE_ID not in text:
            print("FAILED:CNF-0181-probe1 receipt missing case id")
            return 1

    if not payload["pass"]:
        print("FAILED:CNF-0181-probe1 gain or both-states did not hold")
        return 1
    print(
        f"gain {base_ok}/{len(MEASURE_CASES)} -> {imp_ok}/{len(MEASURE_CASES)} "
        f"both_states={both_states} orig_green={orig_invisible}"
    )
    print("SUCCESS:CNF-0181-probe1 independent gain and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
