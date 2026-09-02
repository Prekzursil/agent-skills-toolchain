#!/usr/bin/env python3
"""Live checks for TST-0314 named probes.

Talks to tools/bench/metaloop.py and the independent stats reviewer.
Does not write the catalog receipt, so re-runs after delivery do not
change the receipt hash.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench import metaloop as M  # noqa: E402
from bench import stats_review as R  # noqa: E402

UNIT = "TST-0314"
PREREG = HERE / "fixtures" / "preregistered_thresholds.json"


def _load_prereg() -> dict[str, Any]:
    doc = json.loads(PREREG.read_text(encoding="utf-8"))
    if doc.get("recorded_before_any_ledger_scored") is not True:
        raise RuntimeError("preregistration flag missing")
    return doc


def build_ledgers() -> dict[str, list[dict[str, Any]]]:
    full = M.generate_candidates(n_iterations=8, seed="TST-0314")
    one = M.generate_candidates(n_iterations=1, seed="TST-0314-one")
    return {
        "strict_stable": M.ledger_from_candidates(
            full, gate_name="strict", revert_mode="stable"
        ),
        "strict_degrading": M.ledger_from_candidates(
            full, gate_name="strict", revert_mode="degrading"
        ),
        "permissive": M.ledger_from_candidates(
            full, gate_name="permissive", revert_mode="stable"
        ),
        "single": M.ledger_from_candidates(
            one, gate_name="strict", revert_mode="stable"
        ),
        "candidates_full": full,
        "candidates_one": one,
    }


def series_from_records_checks() -> dict[str, Any]:
    """Catalog: loop metric series computed from decision records, not hand-tallied."""
    ledgers = build_ledgers()
    stable = ledgers["strict_stable"]
    series = M.series_from_records(stable)
    checks: dict[str, Any] = {}

    checks["n_iterations_ge_5"] = series["n_iterations"] >= M.MIN_ITERATIONS
    checks["status_checked"] = series["status"] == "CHECKED"
    checks["source_is_records"] = series["source"] == "decision-records"
    checks["four_metrics_present"] = all(
        {
            "keep_rate",
            "post_keep_regression_rate",
            "iterations_per_accepted_improvement",
            "mean_time_to_revert",
        }.issubset(row.keys())
        for row in series["per_iteration"]
    )

    verify = M.verify_series(series, stable)
    checks["recompute_matches"] = verify["ok"] is True
    checks["not_hand_tallied"] = verify["hand_tallied"] is False

    forged = copy.deepcopy(series)
    if forged["per_iteration"]:
        forged["per_iteration"][0]["keep_rate"] = 0.99
        forged["fingerprint"] = "hand-typed"
    forged_v = M.verify_series(forged, stable)
    checks["forged_series_rejected"] = (
        forged_v["ok"] is False and forged_v["hand_tallied"] is True
    )

    tampered = copy.deepcopy(stable)
    for rec in tampered:
        if rec.get("role") == "gate" and rec.get("decision") == "KEEP":
            rec["decision"] = "REVERT"
            break
    tampered_series = M.series_from_records(tampered)
    checks["tamper_changes_fingerprint"] = (
        tampered_series["fingerprint"] != series["fingerprint"]
    )

    # Independent reviewer recounts KEEP rates from the same records.
    agree = R.series_keep_rates_agree(series, stable)
    checks["reviewer_keep_rates_agree"] = agree["ok"] is True

    gate_ok = R.records_match_reapplied_gate(stable, "strict")
    checks["records_match_reapplied_strict_gate"] = gate_ok["ok"] is True

    # Outcomes of all three classes must appear (a KEEP-only gate is a no-op).
    decisions = {r["decision"] for r in stable if r.get("role") == "gate"}
    checks["all_three_outcomes"] = decisions == {
        "KEEP",
        "REVERT",
        "INSUFFICIENT-EVIDENCE",
    }

    single = M.series_from_records(ledgers["single"])
    checks["single_iteration_not_checked"] = (
        single["status"] == "NOT-CHECKED" and single["checked"] is False
    )
    single_deg = M.detect_degradation(single)
    checks["single_iteration_no_trend_claim"] = single_deg["status"] == "NOT-CHECKED"

    # Round-trip through a JSONL ledger so the series is file-derived.
    tmp = Path(tempfile.mkdtemp(prefix="tst0314-")) / "stable.jsonl"
    M.write_records(tmp, stable)
    loaded = M.load_records(tmp)
    file_series = M.series_from_records(loaded)
    checks["jsonl_roundtrip_fingerprint"] = (
        file_series["fingerprint"] == series["fingerprint"]
    )

    ok = all(bool(v) for v in checks.values())
    return {
        "ok": ok,
        "checks": checks,
        "series": series,
        "single": {
            "status": single["status"],
            "n_iterations": single["n_iterations"],
            "reason": single.get("reason"),
        },
        "reviewer": agree,
        "gate_reapply": gate_ok,
        "n_gate_records": sum(1 for r in stable if r.get("role") == "gate"),
    }


def degradation_control_checks() -> dict[str, Any]:
    """Post-KEEP regression alarm + permissive-gate KEEP-rate jump."""
    prereg = _load_prereg()
    ledgers = build_ledgers()
    checks: dict[str, Any] = {}

    stable_series = M.series_from_records(ledgers["strict_stable"])
    deg_series = M.series_from_records(ledgers["strict_degrading"])
    stable_alarm = M.detect_degradation(stable_series)
    deg_alarm = M.detect_degradation(deg_series)
    checks["stable_post_keep_silent"] = stable_alarm["fired"] is False
    checks["degrading_post_keep_fires"] = deg_alarm["fired"] is True
    checks["degrading_delta_meets_floor"] = (
        float(deg_alarm["delta"]) >= float(prereg["post_keep_regression_delta_min"])
    )
    checks["alarm_is_post_keep_regression"] = (
        deg_alarm.get("alarm") == "post-KEEP-regression-rate"
    )

    jump = M.detect_keep_rate_jump(ledgers["strict_stable"], ledgers["permissive"])
    checks["permissive_jump_fires"] = jump["fired"] is True
    checks["jump_meets_floor"] = float(jump["jump"]) >= float(
        prereg["keep_rate_jump_min"]
    )
    checks["cohens_h_meets_floor"] = float(jump["cohens_h"]) >= float(
        prereg["cohens_h_jump_min"]
    )
    checks["interval_excludes_zero"] = jump["ci_excludes_zero"] is True
    checks["permissive_keep_rate_higher"] = (
        float(jump["keep_rate_permissive"]) > float(jump["keep_rate_strict"])
    )

    # Both-states on the jump detector: strict vs strict must be silent.
    no_jump = M.detect_keep_rate_jump(
        ledgers["strict_stable"], ledgers["strict_stable"]
    )
    checks["strict_vs_strict_silent"] = no_jump["fired"] is False

    reproduced = R.reproduce_jump(ledgers["strict_stable"], ledgers["permissive"])
    checks["reviewer_jump_point_matches"] = (
        abs(float(reproduced["jump"]) - float(jump["jump"])) < 1e-12
    )
    checks["reviewer_h_matches"] = (
        abs(float(reproduced["effect_size_cohens_h"]) - float(jump["cohens_h"]))
        < 1e-12
    )
    checks["reviewer_interval_matches"] = (
        abs(float(reproduced["interval"]["low"]) - float(jump["interval"]["low"]))
        < 1e-12
        and abs(
            float(reproduced["interval"]["high"]) - float(jump["interval"]["high"])
        )
        < 1e-12
    )

    perm_ok = R.records_match_reapplied_gate(ledgers["permissive"], "permissive")
    checks["records_match_reapplied_permissive_gate"] = perm_ok["ok"] is True

    # Rising post-KEEP series is computed from records, not typed.
    v_deg = M.verify_series(deg_series, ledgers["strict_degrading"])
    checks["degrading_series_from_records"] = v_deg["ok"] is True

    ok = all(bool(v) for v in checks.values())
    return {
        "ok": ok,
        "checks": checks,
        "stable_alarm": stable_alarm,
        "degrading_alarm": deg_alarm,
        "jump": jump,
        "reviewer_jump": reproduced,
        "prereg": {
            "keep_rate_jump_min": prereg["keep_rate_jump_min"],
            "cohens_h_jump_min": prereg["cohens_h_jump_min"],
            "post_keep_regression_delta_min": prereg["post_keep_regression_delta_min"],
        },
        "stable_series": stable_series,
        "degrading_series": deg_series,
    }
