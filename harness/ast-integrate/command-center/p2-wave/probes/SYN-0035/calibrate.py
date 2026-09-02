"""Join banded claims to outcomes; hit-rate per band; Brier proper score.

Unadjudicated rows are excluded from rates and counted separately.
Band intervals come from bands.WRITTEN_INTERVALS, never from the data.
"""

from __future__ import annotations

from typing import Any

from bands import (
    BAND_ORDER,
    MIN_N_TO_SCORE,
    POINT_P,
    WRITTEN_DEFINITION_SOURCE,
    WRITTEN_INTERVALS,
)
from fixtures import CALIBRATED_COUNTS, SEED, synthetic_rows
from live_join import ADJUDICATED, input_census, live_evidence_rows


def is_adjudicated(verdict: object) -> bool:
    return str(verdict or "").upper() in ADJUDICATED


def outcome_y(verdict: object) -> int:
    v = str(verdict or "").upper()
    if v == "CONFIRMED":
        return 1
    if v == "REFUTED":
        return 0
    raise ValueError(f"no outcome for unadjudicated verdict {verdict!r}")


def _rate(num: int, den: int) -> dict[str, Any]:
    return {
        "numerator": num,
        "denominator": den,
        "value": (num / den) if den else None,
    }


def band_rows(
    items: list[dict[str, Any]],
    *,
    impute_unadjudicated_as: str | None = None,
) -> list[dict[str, Any]]:
    """Per-band n, hit rate, written interval, inside-interval, unadjudicated.

    impute_unadjudicated_as is the forbidden path (imputed-outcome). The
    published table must call this with None.
    """
    out: list[dict[str, Any]] = []
    for band in BAND_ORDER:
        lo, hi = WRITTEN_INTERVALS[band]
        members = [r for r in items if r.get("band") == band]
        una = [r for r in members if not is_adjudicated(r.get("confirmer_verdict"))]
        adj = [r for r in members if is_adjudicated(r.get("confirmer_verdict"))]
        if impute_unadjudicated_as:
            fake = []
            for r in una:
                cloned = dict(r)
                cloned["confirmer_verdict"] = impute_unadjudicated_as
                fake.append(cloned)
            adj = adj + fake
            una_counted = 0
        else:
            una_counted = len(una)
        confirmed = sum(
            1 for r in adj if str(r.get("confirmer_verdict")).upper() == "CONFIRMED"
        )
        n = len(adj)
        rate = _rate(confirmed, n)
        value = rate["value"]
        inside = value is not None and lo <= value <= hi
        too_small = n < MIN_N_TO_SCORE
        scored = (not too_small) and n > 0
        out.append(
            {
                "band": band,
                "n": n,
                "confirmed": confirmed,
                "refuted": n - confirmed,
                "unadjudicated_n": una_counted,
                "observed_hit_rate": rate,
                "nominal_interval": [lo, hi],
                "point_p": POINT_P[band],
                "inside_nominal_interval": bool(scored and inside),
                "n_too_small": too_small,
                "scored": scored,
                "interval_source": WRITTEN_DEFINITION_SOURCE,
            }
        )
    return out


def unadjudicated_count(items: list[dict[str, Any]]) -> int:
    return sum(1 for r in items if not is_adjudicated(r.get("confirmer_verdict")))


def brier_score(items: list[dict[str, Any]]) -> dict[str, Any]:
    adj = [r for r in items if is_adjudicated(r.get("confirmer_verdict"))]
    if not adj:
        return {"n": 0, "sum_sq": 0.0, "value": None, "rule": "brier"}
    total = 0.0
    for r in adj:
        p = float(POINT_P[str(r["band"])])
        y = float(outcome_y(r.get("confirmer_verdict")))
        total += (p - y) ** 2
    return {
        "n": len(adj),
        "sum_sq": total,
        "value": total / len(adj),
        "rule": "brier",
        "point_p_source": "midpoint of written interval",
    }


def reliability(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Murphy reliability: mean_i (n_i/N) * (p_i - o_i)^2 over scored bands."""
    table = band_rows(items, impute_unadjudicated_as=None)
    n_all = sum(row["n"] for row in table)
    if n_all < 1:
        return {"n": 0, "value": None}
    acc = 0.0
    used = 0
    for row in table:
        if not row["scored"]:
            continue
        o = row["observed_hit_rate"]["value"]
        p = row["point_p"]
        acc += (row["n"] / n_all) * (p - o) ** 2
        used += 1
    return {"n": n_all, "bands_scored": used, "value": acc}


def confusion_matrix(items: list[dict[str, Any]]) -> dict[str, int]:
    tp = fp = fn = tn = 0
    for r in items:
        if not is_adjudicated(r.get("confirmer_verdict")):
            continue
        oracle = r.get("oracle_label")
        if oracle not in ("true", "false"):
            continue
        v = str(r.get("confirmer_verdict")).upper()
        if oracle == "true" and v == "CONFIRMED":
            tp += 1
        elif oracle == "false" and v == "CONFIRMED":
            fp += 1
        elif oracle == "true" and v == "REFUTED":
            fn += 1
        elif oracle == "false" and v == "REFUTED":
            tn += 1
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
    }


def false_pass_rate(matrix: dict[str, int]) -> dict[str, Any]:
    num = int(matrix["false_positive"])
    den = int(matrix["false_positive"]) + int(matrix["true_negative"])
    return _rate(num, den)


def planted_items_for_schema(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Schema planted_items require oracle_label in {true, false}."""
    out = []
    for r in items:
        oracle = r.get("oracle_label")
        if oracle not in ("true", "false"):
            continue
        out.append(
            {
                "claim_id": r["claim_id"],
                "oracle_label": oracle,
                "confirmer_verdict": r["confirmer_verdict"],
                "set_id": r["set_id"],
                "band": r["band"],
            }
        )
    return out


def _test_unadjudicated(items: list[dict[str, Any]], table: list[dict[str, Any]]) -> dict[str, Any]:
    una = [r for r in items if not is_adjudicated(r.get("confirmer_verdict"))]
    published = sum(int(row["unadjudicated_n"]) for row in table)
    reasons = []
    if len(una) < 1:
        reasons.append("no unadjudicated rows in the scoring frame")
    if published != len(una):
        reasons.append(f"unadjudicated published={published} live={len(una)}")
    for row in table:
        band = row["band"]
        adj = [
            r
            for r in items
            if r.get("band") == band and is_adjudicated(r.get("confirmer_verdict"))
        ]
        if row["n"] != len(adj):
            reasons.append(f"{band} n={row['n']} adj={len(adj)}")
    imputed = band_rows(items, impute_unadjudicated_as="REFUTED")
    changed = False
    for a, b in zip(table, imputed):
        if a["observed_hit_rate"] != b["observed_hit_rate"] or a["n"] != b["n"]:
            changed = True
            break
    if not changed:
        reasons.append("imputing REFUTED did not change any rate (vacuous)")
    # Using oracle_label as a stand-in outcome is the other imputation.
    oracle_as_y = 0
    for r in una:
        if r.get("oracle_label") in ("true", "false"):
            oracle_as_y += 1
    if oracle_as_y and any(
        row["n"] != (
            sum(
                1
                for r in items
                if r.get("band") == row["band"]
                and is_adjudicated(r.get("confirmer_verdict"))
            )
        )
        for row in table
    ):
        reasons.append("n folded oracle-only rows")
    ok = not reasons
    return {
        "id": "test_unadjudicated_claims_are_excluded_and_counted_not_imputed",
        "result": "PASS" if ok else "FAIL",
        "unadjudicated_n": len(una),
        "published_unadjudicated_n": published,
        "imputation_changes_rate": changed,
        "detail": reasons,
    }


def _test_synthetic_optimum(items: list[dict[str, Any]]) -> dict[str, Any]:
    syn = [r for r in items if r.get("set_id") == "synthetic-perfect"]
    table = band_rows(syn, impute_unadjudicated_as=None)
    reasons = []
    for row in table:
        band = row["band"]
        want_hit, want_miss = CALIBRATED_COUNTS[band]
        if row["n"] != want_hit + want_miss:
            reasons.append(f"{band} n={row['n']} want={want_hit + want_miss}")
        if row["confirmed"] != want_hit or row["refuted"] != want_miss:
            reasons.append(f"{band} hits={row['confirmed']}/{row['n']}")
        if row["n_too_small"] or not row["scored"]:
            reasons.append(f"{band} not scored")
        if not row["inside_nominal_interval"]:
            reasons.append(f"{band} rate outside written interval")
        if list(row["nominal_interval"]) != list(WRITTEN_INTERVALS[band]):
            reasons.append(f"{band} interval mutated")
    brier = brier_score(syn)
    independent = 0.0
    n = 0
    for r in syn:
        if not is_adjudicated(r.get("confirmer_verdict")):
            continue
        p = POINT_P[str(r["band"])]
        y = float(outcome_y(r.get("confirmer_verdict")))
        independent += (p - y) ** 2
        n += 1
    independent_value = independent / n if n else None
    if brier["value"] is None or independent_value is None:
        reasons.append("brier missing")
    elif abs(float(brier["value"]) - float(independent_value)) > 1e-12:
        reasons.append("brier != independent recompute")
    ok = not reasons
    return {
        "id": "synthetic_control_perfectly_calibrated_scores_at_optimum",
        "result": "PASS" if ok else "FAIL",
        "brier": brier,
        "independent_brier": independent_value,
        "all_bands_inside_written_interval": all(
            row["inside_nominal_interval"] for row in table
        ),
        "detail": reasons,
    }


def _test_intervals_from_definition(
    items: list[dict[str, Any]], table: list[dict[str, Any]]
) -> dict[str, Any]:
    reasons = []
    likely = WRITTEN_INTERVALS["likely"]
    if likely != (0.55, 0.80):
        reasons.append("likely is not the catalog-cited 55-80 percent")
    for row in table:
        band = row["band"]
        written = list(WRITTEN_INTERVALS[band])
        if list(row["nominal_interval"]) != written:
            reasons.append(f"{band} published {row['nominal_interval']} != {written}")
        obs = row["observed_hit_rate"]["value"]
        if obs is not None and list(row["nominal_interval"]) == [obs, obs]:
            if written != [obs, obs]:
                reasons.append(f"{band} interval collapsed to observed rate")
    # A data-fitted interval would track the live almost-certain 1.0.
    live = [r for r in items if r.get("set_id") == "live-success-receipt-evidence"]
    live_ac = [
        r
        for r in live
        if r.get("band") == "almost-certain" and is_adjudicated(r.get("confirmer_verdict"))
    ]
    if live_ac:
        live_rate = sum(
            1 for r in live_ac if str(r.get("confirmer_verdict")).upper() == "CONFIRMED"
        ) / len(live_ac)
        ac_interval = tuple(next(r["nominal_interval"] for r in table if r["band"] == "almost-certain"))
        if ac_interval == (live_rate, live_rate) and WRITTEN_INTERVALS["almost-certain"] != (
            live_rate,
            live_rate,
        ):
            reasons.append("almost-certain interval fitted to live rate")
    ok = not reasons
    return {
        "id": "test_band_intervals_come_from_the_written_definition_not_from_the_data",
        "result": "PASS" if ok else "FAIL",
        "written_likely": list(likely),
        "detail": reasons,
    }


def run_calibration(repo) -> dict[str, Any]:
    synthetic = synthetic_rows()
    live = live_evidence_rows(repo)
    # Combined frame for the unadjudicated-exclusion test only. The published
    # program table is live; the scorer-control table is synthetic. Mixing
    # SUCCESS-receipt hits into the synthetic arm would hide a 30/30 ceiling.
    frame = synthetic + live
    syn_table = band_rows(synthetic, impute_unadjudicated_as=None)
    live_table = band_rows(live, impute_unadjudicated_as=None)
    table = band_rows(frame, impute_unadjudicated_as=None)
    syn_adj = [r for r in synthetic if r.get("set_id") == "synthetic-perfect"]
    tests = [
        _test_unadjudicated(synthetic, syn_table),
        _test_synthetic_optimum(synthetic),
        _test_intervals_from_definition(frame, syn_table),
    ]
    matrix = confusion_matrix(synthetic)
    planted = planted_items_for_schema(synthetic)
    census = input_census(repo)
    note_bits = ["Live join is SUCCESS-receipt evidence[] only."]
    if not census["claim_registry"].get("exists"):
        note_bits.append("CLAIM-REGISTRY.json is absent.")
    if census["adversarial_dir"].get("exists"):
        note_bits.append(
            "command-center/adversarial exists but those files are not "
            "claim-level Sherman-Kent band + refuter-verdict rows, so they "
            "are not joined."
        )
    else:
        note_bits.append(
            "command-center/adversarial (B10 refuter verdicts) is absent."
        )
    if census["confirmation_dir"].get("exists"):
        note_bits.append(
            "command-center/confirmation exists but those files are not "
            "claim-level Sherman-Kent band + confirmer-verdict rows, so they "
            "are not joined."
        )
    note_bits.append(
        "A frame with no REFUTED class cannot answer whether 'likely' meant "
        "55-80 percent in practice for the program. The synthetic-perfect "
        "arm validates the scorer, not the estate."
    )
    return {
        "seed": SEED,
        "input_census": census,
        "written_intervals": {k: list(v) for k, v in WRITTEN_INTERVALS.items()},
        "written_definition_source": WRITTEN_DEFINITION_SOURCE,
        "point_p": dict(POINT_P),
        "min_n_to_score": MIN_N_TO_SCORE,
        "synthetic": synthetic,
        "live": live,
        "frame": frame,
        "bands": live_table,
        "live_bands": live_table,
        "synthetic_bands": syn_table,
        "unadjudicated_count": unadjudicated_count(synthetic),
        "unadjudicated_count_live": unadjudicated_count(live),
        "unadjudicated_count_combined": unadjudicated_count(frame),
        "unadjudicated_synthetic": unadjudicated_count(synthetic),
        "unadjudicated_live": unadjudicated_count(live),
        "proper_score": {
            "combined_adjudicated": brier_score(frame),
            "synthetic_perfect": brier_score(syn_adj),
            "live_success_receipt_evidence": brier_score(live),
        },
        "reliability": {
            "combined": reliability(frame),
            "synthetic_perfect": reliability(syn_adj),
            "live_success_receipt_evidence": reliability(live),
        },
        "confusion_matrix": matrix,
        "false_pass_rate": false_pass_rate(matrix),
        "planted_items": planted,
        "tests": tests,
        "sampling_frame_note": " ".join(note_bits),
    }


def tests_pass(cal: dict[str, Any]) -> bool:
    tests = cal.get("tests") or []
    if len(tests) < 3:
        return False
    return all(t.get("result") == "PASS" for t in tests)
