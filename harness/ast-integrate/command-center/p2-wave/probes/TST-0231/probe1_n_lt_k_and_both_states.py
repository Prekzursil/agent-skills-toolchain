#!/usr/bin/env python3
"""Probe 1: gate refuses n<k; 20% regression is caught; 2% noise is not.

Signal (a): refusal at n<k, including a 50% shift that a single-sample
comparator would flag. Both-states control from tests_required.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import distribution_gate as G  # noqa: E402

UNIT = "TST-0231"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    k = G.DEFAULT_K
    refusals = G.n_lt_k_controls(k=k)
    single = refusals["single_sample"]
    short = refusals["n_k_minus_1_with_50pct"]
    ok_n = refusals["n_equals_k_no_change"]

    if single["verdict"] != "REFUSED" or single.get("reason") != "n<k":
        return fail(f"n=1 not refused: {single}")
    if single.get("issued") is True:
        return fail("n=1 issued a verdict")
    if single["n_baseline"] != 1 or single["n_candidate"] != 1:
        return fail(f"n=1 counts {single['n_baseline']} {single['n_candidate']}")

    if short["verdict"] != "REFUSED" or short.get("reason") != "n<k":
        return fail(f"n=k-1 50pct shift was scored instead of refused: {short}")
    if short["n_baseline"] != k - 1:
        return fail(f"expected n=k-1 got {short['n_baseline']}")

    if ok_n["verdict"] != "NO_REGRESSION" or not ok_n.get("issued"):
        return fail(f"n=k no-change did not issue NO_REGRESSION: {ok_n}")
    for side in ("baseline", "candidate"):
        block = ok_n[side]
        for field in ("median", "p95", "variance", "stdev", "iqr"):
            if field not in block or block[field] is None:
                return fail(f"n=k missing spread/point field {side}.{field}")

    states = G.both_states_controls(k=k)
    reg = states["regression_20pct"]
    noise = states["noise_2pct"]
    if reg["verdict"] != "REGRESSION" or not reg.get("issued"):
        return fail(f"20pct regression not caught: {reg}")
    if abs(reg["median_relative_change"] - 0.20) > 1e-12:
        return fail(f"20pct median rel {reg['median_relative_change']}")
    if abs(reg["p95_relative_change"] - 0.20) > 1e-12:
        return fail(f"20pct p95 rel {reg['p95_relative_change']}")
    if noise["verdict"] != "NO_REGRESSION":
        return fail(f"2pct noise flagged: {noise}")
    if not noise.get("inside_noise_band"):
        return fail("2pct case not inside stated noise band")
    if abs(noise["median_relative_change"] - 0.02) > 1e-12:
        return fail(f"2pct median rel {noise['median_relative_change']}")

    if "stated_variance" not in reg or reg["stated_variance"]["baseline"] is None:
        return fail("20pct case missing stated variance")

    payload = {
        "probe": "probe1-n-lt-k-and-both-states",
        "unit_id": UNIT,
        "k": k,
        "single_sample_verdict": single["verdict"],
        "n_k_minus_1_verdict": short["verdict"],
        "n_equals_k_verdict": ok_n["verdict"],
        "regression_20pct": reg["verdict"],
        "noise_2pct": noise["verdict"],
        "spread_reported": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"k={k} n1={single['verdict']} n_k-1={short['verdict']} "
        f"n_k={ok_n['verdict']} 20pct={reg['verdict']} 2pct={noise['verdict']}"
    )
    print(f"SUCCESS:{UNIT}-probe1 n<k refused; 20pct caught; 2pct not flagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
