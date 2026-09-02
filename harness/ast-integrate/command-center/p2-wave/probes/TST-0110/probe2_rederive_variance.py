#!/usr/bin/env python3
"""Probe 2: statistics reviewer re-derives the variance band from raw numbers.

The summary mean/std/mde/delta/verdict fields are not evidence. This probe
recomputes them from baseline.raw / null.raw / mechanism.raw and independently
re-runs the harness. A summary that disagrees with its own raw array fails.
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
import stats as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0110.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0110-probe2 {msg}")
    return 1


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(float(a) - float(b)) <= tol


def from_raw(base_raw, null_raw, mech_raw) -> dict:
    base = S.rederive(base_raw)
    null = S.rederive(null_raw)
    mech = S.rederive(mech_raw)
    band = base["mde"]
    nd = null["mean"] - base["mean"]
    md = mech["mean"] - base["mean"]
    return {
        "mean": base["mean"],
        "std": base["std"],
        "mde": band,
        "null_delta": nd,
        "mech_delta": md,
        "null_sig": S.significant(nd, band),
        "mech_sig": S.significant(md, band),
        "verdict": D.classify(nd, md, band),
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0110" not in json.dumps(doc):
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    pay = D.receipt_payload(doc)
    if int(pay.get("seed") or 0) != H.SEED:
        return fail("seed mismatch")

    live = D.measure_all()
    live_by = {r["name"]: r for r in live["rows"]}
    derived_gameable: list[str] = []
    benches = list(pay.get("benchmarks") or [])
    if len(benches) < 4:
        return fail(f"benchmarks={len(benches)} want>=4")

    for b in benches:
        name = b["name"]
        raw_b = list(b["baseline"]["raw"])
        raw_n = list(b["null_change"]["raw"])
        raw_m = list(b["mechanism_change"]["raw"])
        if len(raw_b) < 5 or len(raw_n) < 5 or len(raw_m) < 5:
            return fail(f"{name} raw too short")
        got = from_raw(raw_b, raw_n, raw_m)
        print(
            f"rederive {name} n_inputs={b.get('n_inputs')} "
            f"mean={got['mean']} std={got['std']} mde={got['mde']} "
            f"null_delta={got['null_delta']} mech_delta={got['mech_delta']} "
            f"verdict={got['verdict']} summary_verdict={b.get('verdict')}"
        )
        if not close(b["baseline"]["mean"], got["mean"]):
            return fail(f"{name} baseline.mean is not mean(raw)")
        if not close(b["baseline"]["std"], got["std"]):
            return fail(f"{name} baseline.std is not stdev(raw)")
        if not close(b["variance_band"]["mde"], got["mde"]):
            return fail(f"{name} variance_band.mde is not mde(raw)")
        if not close(b["null_change"]["delta"], got["null_delta"]):
            return fail(f"{name} null.delta disagrees with raw")
        if not close(b["mechanism_change"]["delta"], got["mech_delta"]):
            return fail(f"{name} mechanism.delta disagrees with raw")
        if b["null_change"]["significant"] is not got["null_sig"]:
            return fail(f"{name} null.significant disagrees with raw")
        if b["mechanism_change"]["significant"] is not got["mech_sig"]:
            return fail(f"{name} mechanism.significant disagrees with raw")
        if b["verdict"] != got["verdict"]:
            return fail(f"{name} verdict {b['verdict']} != rederived {got['verdict']}")
        if got["verdict"] == "GAMEABLE":
            derived_gameable.append(name)

        live_row = live_by.get(name)
        if live_row is None:
            return fail(f"{name} missing from live re-run")
        if list(live_row["baseline"]["raw"]) != raw_b:
            return fail(f"{name} live baseline.raw != receipt raw (same seed must reproduce)")
        if live_row["verdict"] != got["verdict"]:
            return fail(f"{name} live verdict drifted")

    named = list(pay.get("gameable_named") or [])
    if sorted(named) != sorted(derived_gameable):
        return fail(f"gameable_named={named} rederived={derived_gameable}")
    if "workflow_stage_count" not in derived_gameable:
        return fail("rederived GAMEABLE set missing workflow_stage_count")

    # Mutant: trust the summary mean, ignore raw. Must go red.
    mutant = json.loads(json.dumps(benches[0]))
    mutant["baseline"]["mean"] = float(mutant["baseline"]["mean"]) + 999.0
    mutant_got = from_raw(
        mutant["baseline"]["raw"],
        mutant["null_change"]["raw"],
        mutant["mechanism_change"]["raw"],
    )
    if close(mutant["baseline"]["mean"], mutant_got["mean"]):
        return fail("summary-mean mutant was not distinguishable from raw")
    print("summary_mean_mutant_killed=True")
    print(f"gameable_named={derived_gameable}")
    print("statistics_reviewer=PASS re-derived from raw not from summary")
    print("SUCCESS:TST-0110-probe2 variance re-derived GAMEABLE named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
