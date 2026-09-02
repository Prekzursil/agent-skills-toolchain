#!/usr/bin/env python3
"""Probe 1: seeded stratified sample + per-stratum Wilson intervals.

Catalog tests:
  * Stratified sample drawn by a recorded random seed, not by hand-picking.
  * Error rate per stratum with intervals.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0323"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0323.json"

sys.path.insert(0, str(HERE))
import adjudicate as A  # noqa: E402
import ledger as L  # noqa: E402
import prereg as P  # noqa: E402
import sample as S  # noqa: E402
import strata as ST  # noqa: E402
import wilson as W  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    prereg = P.load_prereg()
    proto = P.load_protocol()
    if proto["blinding"]["adjudicator_sees_platform_verdict"] is not False:
        return fail("protocol not blind")

    z = W.Z_95
    w0 = W.wilson_interval(0, 8, z)
    closed = W.wilson_zero_n_high(8, z)
    print(f"wilson_0_8 low={w0['low']:.12f} high={w0['high']:.12f} closed={closed:.12f}")
    if abs(w0["low"] - 0.0) > 1e-12:
        return fail("wilson 0/8 low is not 0")
    if abs(w0["high"] - closed) > 1e-12:
        return fail("wilson 0/8 high does not match z^2/(n+z^2)")
    if w0["high"] <= 0:
        return fail("wilson 0/8 collapsed to Wald [0,0]")
    wn = W.wilson_interval(8, 8, z)
    if abs(wn["high"] - 1.0) > 1e-12 or abs(wn["low"] - (1.0 - closed)) > 1e-9:
        # low for k=n is 1 - z^2/(n+z^2)
        if abs(wn["high"] - 1.0) > 1e-12:
            return fail("wilson 8/8 high is not 1")

    pop = L.load_population()
    rows = pop["rows"]
    part = ST.partition(rows)
    print(
        f"partition ok={part['ok']} n={part['n']} counts={part['counts']} "
        f"unmatched={len(part['unmatched'])}"
    )
    if not part["ok"] or part["n"] != 80:
        return fail("synthetic population is not a 2x2 partition of 80")
    if sum(part["counts"].values()) != 80:
        return fail("stratum counts do not sum to n")

    seed = int(prereg["frame_seed"])
    n_take = int(prereg["n_per_stratum"])
    drawn = S.draw_frame(rows, n_take, seed)
    drawn_again = S.draw_frame(rows, n_take, seed)
    if drawn["sampled_ids_by_stratum"] != drawn_again["sampled_ids_by_stratum"]:
        return fail("same seed did not reproduce the sample")
    other = S.draw_frame(rows, n_take, seed + 1)
    if other["sampled_ids_by_stratum"] == drawn["sampled_ids_by_stratum"]:
        return fail("seed+1 produced the identical sample; draw is not using the seed")

    by_id = {str(r["case_id"]): r for r in rows}
    rates = S.stratum_rates(drawn["sampled_ids_by_stratum"], by_id)
    for row in rates:
        print(
            f"stratum {row['stratum_id']} k={row['k']} n={row['n']} "
            f"rate={row['rate']} low={row['interval']['low']:.6f} "
            f"high={row['interval']['high']:.6f}"
        )
        if not row["defined"] or row["n"] != n_take:
            return fail(f"{row['stratum_id']} missing interval")
        if row["interval"]["method"] != "wilson_score":
            return fail("interval method is not wilson_score")

    judged_fail = next(r for r in rates if r["stratum_id"] == "judged:fail")
    det_pass = next(r for r in rates if r["stratum_id"] == "deterministic:pass")
    threshold = float(prereg["error_rate_threshold"])
    if not (judged_fail["rate"] > threshold):
        return fail("judged:fail sample did not exceed the pre-registered threshold")
    if det_pass["rate"] != 0.0:
        return fail("deterministic:pass should be a zero-error stratum")

    all_sample = [by_id[i] for ids in drawn["sampled_ids_by_stratum"].values() for i in ids]
    pooled = A.error_counts(all_sample)
    print(f"pooled_unstratified k={pooled['k']} n={pooled['n']} rate={pooled['rate']}")

    if not RECEIPT.is_file():
        return fail("receipt missing; cannot recompute published intervals")
    rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
    design = P.receipt_field(rec, "sample_design") or {}
    if not isinstance(design, dict):
        return fail("receipt sample_design missing")
    if design.get("seed") != seed:
        return fail("receipt sample_design.seed does not match prereg")
    if design.get("n_per_stratum") != n_take:
        return fail("receipt n_per_stratum does not match prereg")
    if design.get("selection_method") != prereg["selection_method"]:
        return fail("receipt selection_method does not match prereg")
    if "error_rate" in design or "stratum_error_rates" in design:
        return fail("sample_design must not carry computed rates")
    published_ids = design.get("sampled_case_ids_by_stratum") or {}
    if published_ids != drawn["sampled_ids_by_stratum"]:
        return fail("receipt sample ids do not match a fresh draw of the recorded seed")

    pub_rates = P.receipt_field(rec, "stratum_error_rates") or []
    if not isinstance(pub_rates, list) or len(pub_rates) != 4:
        return fail("receipt missing four stratum_error_rates")
    for row in rates:
        pub = next((p for p in pub_rates if p.get("stratum_id") == row["stratum_id"]), None)
        if pub is None:
            return fail(f"receipt missing {row['stratum_id']}")
        if int(pub["k"]) != row["k"] or int(pub["n"]) != row["n"]:
            return fail(f"receipt k/n mismatch on {row['stratum_id']}")
        recomputed = W.wilson_interval(int(pub["k"]), int(pub["n"]))
        if abs(recomputed["low"] - float(pub["interval"]["low"])) > 1e-12:
            return fail(f"reviewer wilson low mismatch {row['stratum_id']}")
        if abs(recomputed["high"] - float(pub["interval"]["high"])) > 1e-12:
            return fail(f"reviewer wilson high mismatch {row['stratum_id']}")
        if abs(recomputed["rate"] - float(pub["rate"])) > 1e-12:
            return fail(f"reviewer rate mismatch {row['stratum_id']}")

    prereg_sha, _ = P.sha256_file(P.PREREG_PATH)
    cited_block = P.receipt_field(rec, "threshold_preregistration") or {}
    cited = cited_block.get("prereg_sha256") if isinstance(cited_block, dict) else None
    if cited != prereg_sha:
        return fail("receipt prereg_sha256 does not match threshold_prereg.json")
    if not isinstance(cited_block, dict) or cited_block.get("recorded_before_computation") is not True:
        return fail("threshold not marked recorded_before_computation")

    print(
        json.dumps(
            {
                "judged_fail_rate": judged_fail["rate"],
                "pass": True,
                "pooled_rate": pooled["rate"],
                "probe": "probe1-seeded-sample",
                "same_seed_identical": True,
                "seed_plus_one_differs": True,
                "unit_id": UNIT,
                "wilson_0_8_not_wald": w0["high"] > 0,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT}-probe1 seeded-sample+wilson")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
