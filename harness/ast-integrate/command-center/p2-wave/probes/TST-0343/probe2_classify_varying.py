#!/usr/bin/env python3
"""Probe 2: classify every varying test as flaky-C11 or narrow-assertion.

Independent statistics re-derivation from the raw per-seed matrix:
pass-rate, Wilson 95% interval, Cohen's h vs always-pass. Must match the
live classifier, not the receipt summary.

Catalog tests_required[1]: classification of every varying test with evidence.
Retry policy: same-seed disagreement is a detector failure (flaky-C11).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import seed_registry as SR  # noqa: E402

ART = REPO / "command-center/receipts/TST-0343.json"
OUT = HERE / "probe2-classify-varying.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0343-probe2 {msg}")
    return 1


def stats_equal(a: dict, b: dict) -> bool:
    for key in ("k", "n"):
        if int(a[key]) != int(b[key]):
            return False
    for key in ("p", "lo", "hi", "cohens_h_vs_always_pass"):
        if round(float(a[key]), 6) != round(float(b[key]), 6):
            return False
    return True


def main() -> int:
    report = SR.run_sweep()
    varying = [r for r in report["rows"] if r["class"] != SR.STABLE]
    if len(varying) < 2:
        return fail(f"expected planted narrow + planted flake, varying={len(varying)}")

    for row in varying:
        if row["class"] not in {SR.NARROW, SR.FLAKY}:
            return fail(f"{row['id']} class={row['class']}")
        # Re-derive stats from raw per_seed only.
        k = sum(1 for v in row["per_seed"].values() if v == "PASS")
        n = len(row["per_seed"])
        derived = SR.wilson_interval(k, n)
        derived["cohens_h_vs_always_pass"] = SR.cohens_h(derived["p"], 1.0)
        if not stats_equal(derived, row["stats"]):
            return fail(f"stats mismatch {row['id']} live={row['stats']} derived={derived}")
        if row["class"] == SR.NARROW:
            if not row["same_seed_reproducible"]:
                return fail(f"{row['id']} classified narrow but same-seed unreproducible")
            if not row["varies_across_seeds"]:
                return fail(f"{row['id']} classified narrow but does not vary across seeds")
        if row["class"] == SR.FLAKY:
            if row["same_seed_reproducible"]:
                return fail(f"{row['id']} classified flaky but same-seed reproducible")
            if not row["flake_seeds"]:
                return fail(f"{row['id']} flaky without flake_seeds evidence")

    planted_n = next(r for r in report["rows"] if r["id"] == SR.PLANTED_NARROW_ID)
    planted_f = next(r for r in report["rows"] if r["id"] == SR.PLANTED_FLAKE_ID)
    if planted_n["class"] != SR.NARROW:
        return fail(f"planted narrow class={planted_n['class']}")
    if planted_f["class"] != SR.FLAKY:
        return fail(f"planted flake class={planted_f['class']}")
    if not report["planted_flake_detected"]:
        return fail("planted C11 flake not detected")

    # Both-states on the classifier: a stable all-PASS row must NOT be
    # classified as varying; the planted varying rows MUST.
    stable = next(r for r in report["rows"] if r["id"] == "test_arithmetic_stable")
    if stable["class"] != SR.STABLE:
        return fail("good-state stable test was classified as varying")
    if planted_n["class"] == SR.STABLE or planted_f["class"] == SR.STABLE:
        return fail("bad-state planted tests classified stable")

    # Same-seed re-run of the narrow test at the lucky seed stays PASS.
    lucky = str(SR.PLANTED_NARROW_SEED)
    reps = planted_n["same_seed_repeats"][lucky]
    if set(reps) != {"PASS"}:
        return fail(f"narrow lucky-seed repeats not all PASS: {reps}")

    payload = {
        "probe": "probe2-classify-varying",
        "unit_id": "TST-0343",
        "pass": True,
        "classifications": [
            {
                "id": r["id"],
                "class": r["class"],
                "undeclared_sensitivity": r["undeclared_sensitivity"],
                "pass_count": r["pass_count"],
                "n_seeds": r["n_seeds"],
                "stats": r["stats"],
                "flake_seeds": r["flake_seeds"],
                "evidence": (
                    "same-seed repeats disagree"
                    if r["class"] == SR.FLAKY
                    else "same seed reproducible; outcomes differ across seeds"
                    if r["class"] == SR.NARROW
                    else "identical outcome on every recorded seed"
                ),
            }
            for r in report["rows"]
        ],
        "narrow_assertion_ids": report["narrow_assertion_ids"],
        "flaky_c11_ids": report["flaky_c11_ids"],
        "undeclared_ids": report["undeclared_ids"],
        "planted_narrow_class": planted_n["class"],
        "planted_flake_class": planted_f["class"],
        "reviewer_rederived_from_raw_matrix": True,
        "negative_control": {
            "id": "NC-STABLE-NOT-CLASSIFIED-VARYING",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
        },
    }

    if ART.is_file():
        receipt = json.loads(ART.read_text(encoding="utf-8"))
        if "SUCCESS:TST-0343" not in ART.read_text(encoding="utf-8"):
            return fail("sentinel-absent")
        live = (receipt.get("report") or {}).get("sweep") or {}
        if live.get("narrow_assertion_ids") != report["narrow_assertion_ids"]:
            return fail("receipt narrow ids disagree")
        if live.get("flaky_c11_ids") != report["flaky_c11_ids"]:
            return fail("receipt flaky ids disagree")
        rec_rows = {
            r["id"]: r
            for r in ((receipt.get("report") or {}).get("rows") or [])
            if isinstance(r, dict)
        }
        for r in report["rows"]:
            rr = rec_rows.get(r["id"]) or {}
            if rr.get("class") != r["class"]:
                return fail(f"receipt class {r['id']} {rr.get('class')} != live {r['class']}")
            if rr.get("stats") and not stats_equal(rr["stats"], r["stats"]):
                return fail(f"receipt stats {r['id']} disagree with live re-derivation")
        payload["receipt_matches_live"] = True
    else:
        payload["receipt_matches_live"] = False

    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(
        f"narrow={report['narrow_assertion_ids']} flaky={report['flaky_c11_ids']} "
        f"undeclared={report['undeclared_ids']}"
    )
    print("SUCCESS:TST-0343-probe2 varying tests classified; stats re-derived from raw matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
